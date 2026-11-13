import { Route, Routes } from 'react-router-dom'
import AppLayout from './layouts/AppLayout'
import DashboardPage from './pages/DashboardPage'
import ManualReviewsPage from './pages/ManualReviewsPage'
import NotFoundPage from './pages/NotFoundPage'
import RequestDetailsPage from './pages/RequestDetailsPage'
import SubmitRequestPage from './pages/SubmitRequestPage'
import WorkflowConfigurationPage from './pages/WorkflowConfigurationPage'

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<DashboardPage />} />
        <Route path="submit" element={<SubmitRequestPage />} />
        <Route path="requests" element={<RequestDetailsPage />} />
        <Route path="reviews" element={<ManualReviewsPage />} />
        <Route path="workflows" element={<WorkflowConfigurationPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
