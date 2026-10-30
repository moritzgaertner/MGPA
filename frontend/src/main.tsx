import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import App from '@/App'
import { Provider } from '@/components/ui/provider'

// Entry point: mount the React app into <div id="root"> from index.html.
// Provider = Chakra UI theme + dark mode for everything inside it.
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Provider>
      <App />
    </Provider>
  </StrictMode>,
)
