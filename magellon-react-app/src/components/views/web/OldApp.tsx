import { useState } from 'react'
import reactLogo from '../../../assets/images/react.svg'
import viteLogo from '/vite.svg'
import '../../../assets/css/App.css'
import {useTranslation} from "react-i18next";
import '../../../core/i18n.ts';

function OldApp() {
  const [count, setCount] = useState(0)
    const { t, i18n } = useTranslation();
  return (
    <>

      <div>
          <h1>{t('global.menu.account.main')}</h1>

        <a href="https://vitejs.dev" target="_blank">
          <img src={viteLogo} className="logo" alt="Vite logo" />
        </a>
        <a href="https://react.dev" target="_blank">
          <img src={reactLogo} className="logo react" alt="React logo" />
        </a>
      </div>
      <h1>Vite + React</h1>
      <div className="card">
        <button onClick={() => setCount((count) => count + 1)}>
          count is {count}
        </button>
        <p>
          Edit <code>src/App.tsx</code> and save to test HMR
        </p>
      </div>
      <p className="read-the-docs">
        Click on the Vite and React logos to learn more
      </p>
    </>
  )
}

export default OldApp
