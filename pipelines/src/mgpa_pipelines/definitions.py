"""Dagster definitions: document ingestion as a partitioned asset, triggered by a sensor.

Each uploaded document is one partition of the `document_chunks` asset ("the chunks + embeddings
of document 42"). The sensor polls Postgres for `pending` documents, registers their partition and
requests a run; the asset reads, chunks and embeds the document via the backend's ingestion code.
Dagster adds run history, retries from the UI and per-document lineage on top.
"""

import dagster as dg
from mgpa_backend.db import SessionLocal
from mgpa_backend.knowledge.embeddings import Embedder, get_embedder
from mgpa_backend.knowledge.ingest import ingest_document, pending_documents

DOCUMENTS = "documents"
documents_partitions = dg.DynamicPartitionsDefinition(name=DOCUMENTS)


class EmbedderResource(dg.ConfigurableResource):  # type: ignore[type-arg]
    """Provides the embedding client. Tests swap in a subclass that returns a fake."""

    def get(self) -> Embedder:
        return get_embedder()


@dg.asset(
    partitions_def=documents_partitions,
    description="Chunks and Voyage embeddings of one uploaded document, stored in pgvector.",
    retry_policy=dg.RetryPolicy(max_retries=2, delay=10),
)
def document_chunks(
    context: dg.AssetExecutionContext, embedder: EmbedderResource
) -> dg.MaterializeResult:  # type: ignore[type-arg]
    document_id = int(context.partition_key)
    with SessionLocal() as db:
        count = ingest_document(db, document_id, embedder.get())
    return dg.MaterializeResult(metadata={"chunks": count})


ingest_job = dg.define_asset_job("ingest_documents", selection=[document_chunks])


@dg.sensor(
    job=ingest_job,
    minimum_interval_seconds=10,
    default_status=dg.DefaultSensorStatus.RUNNING,  # active without clicking in the UI
)
def pending_documents_sensor(
    context: dg.SensorEvaluationContext,
) -> dg.SensorResult | dg.SkipReason:
    with SessionLocal() as db:
        pending = pending_documents(db)
    if not pending:
        return dg.SkipReason("No pending documents")

    keys = [str(document_id) for document_id, _ in pending]
    new_keys = [key for key in keys if not context.instance.has_dynamic_partition(DOCUMENTS, key)]
    return dg.SensorResult(
        # run_key = document + its last change: the same request never runs twice, while a
        # "re-process" (which bumps updated_at) does start a new run.
        run_requests=[
            dg.RunRequest(partition_key=str(document_id), run_key=f"{document_id}@{updated_at}")
            for document_id, updated_at in pending
        ],
        dynamic_partitions_requests=(
            [documents_partitions.build_add_request(new_keys)] if new_keys else []
        ),
    )


defs = dg.Definitions(
    assets=[document_chunks],
    jobs=[ingest_job],
    sensors=[pending_documents_sensor],
    resources={"embedder": EmbedderResource()},
)
