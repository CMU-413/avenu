import { BrowserRouter, Routes, Route } from 'react-router-dom'
import './App.css'
import AdminMailIntakeForm from './AdminMailIntakeForm'

// const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:5001'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/mailIntake/:mailboxId" element={<AdminMailIntakeForm />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App