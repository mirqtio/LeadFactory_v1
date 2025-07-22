/**
 * Main App Component
 * Sets up React Router and provides the global navigation shell
 */
import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AppShell, PublicShell, AuthenticatedShell, AdminShell } from '@/components'
import './styles/globals.css'

// Placeholder pages for demonstration
const DashboardPage = () => (
  <div className="space-y-6">
    <h1 className="text-h1">Dashboard</h1>
    <p className="text-body">Welcome to the LeadFactory dashboard. This is where you'll find key metrics and insights about your lead generation activities.</p>
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      <div className="card">
        <h3 className="text-h3 mb-2">Total Leads</h3>
        <p className="text-2xl font-bold text-synthesis-blue">1,247</p>
      </div>
      <div className="card">
        <h3 className="text-h3 mb-2">Conversion Rate</h3>
        <p className="text-2xl font-bold text-semantic-success">24.5%</p>
      </div>
      <div className="card">
        <h3 className="text-h3 mb-2">Active Campaigns</h3>
        <p className="text-2xl font-bold text-neutral">12</p>
      </div>
    </div>
  </div>
)

const LeadsPage = () => (
  <div className="space-y-6">
    <h1 className="text-h1">Lead Management</h1>
    <p className="text-body">Manage and track your leads through the sales pipeline.</p>
    <div className="card">
      <p className="text-center text-neutral py-12">Lead management interface would be implemented here.</p>
    </div>
  </div>
)

const CampaignsPage = () => (
  <div className="space-y-6">
    <h1 className="text-h1">Marketing Campaigns</h1>
    <p className="text-body">Create, manage, and analyze your marketing campaigns.</p>
    <div className="card">
      <p className="text-center text-neutral py-12">Campaign management interface would be implemented here.</p>
    </div>
  </div>
)

const AnalyticsPage = () => (
  <div className="space-y-6">
    <h1 className="text-h1">Analytics</h1>
    <p className="text-body">Deep insights into your lead generation performance.</p>
    <div className="card">
      <p className="text-center text-neutral py-12">Analytics dashboard would be implemented here.</p>
    </div>
  </div>
)

const ReportsPage = () => (
  <div className="space-y-6">
    <h1 className="text-h1">Reports</h1>
    <p className="text-body">Generate and view detailed reports on your activities.</p>
    <div className="card">
      <p className="text-center text-neutral py-12">Reports interface would be implemented here.</p>
    </div>
  </div>
)

const AdminPage = () => (
  <div className="space-y-6">
    <h1 className="text-h1">Administration</h1>
    <p className="text-body">System administration and configuration.</p>
    <div className="card">
      <p className="text-center text-neutral py-12">Admin interface would be implemented here.</p>
    </div>
  </div>
)

const LoginPage = () => (
  <div className="min-h-screen flex items-center justify-center bg-neutral-50 dark:bg-neutral-900">
    <div className="card max-w-md w-full mx-4">
      <div className="text-center mb-8">
        <div className="flex items-center justify-center space-x-2 mb-4">
          <span className="text-4xl">🏭</span>
          <h1 className="text-h2">LeadFactory</h1>
        </div>
        <p className="text-neutral">Sign in to your account</p>
      </div>
      
      <form className="space-y-4">
        <div>
          <label htmlFor="email" className="block text-sm font-medium text-neutral mb-2">
            Email address
          </label>
          <input
            id="email"
            type="email"
            required
            className="input w-full"
            placeholder="Enter your email"
          />
        </div>
        
        <div>
          <label htmlFor="password" className="block text-sm font-medium text-neutral mb-2">
            Password
          </label>
          <input
            id="password"
            type="password"
            required
            className="input w-full"
            placeholder="Enter your password"
          />
        </div>
        
        <button
          type="submit"
          className="btn-primary w-full"
        >
          Sign In
        </button>
      </form>
      
      <div className="mt-6 text-center">
        <p className="text-sm text-neutral">
          Don't have an account?{' '}
          <a href="#" className="text-synthesis-blue hover:underline">
            Contact your administrator
          </a>
        </p>
      </div>
    </div>
  </div>
)

const HomePage = () => (
  <div className="min-h-screen bg-gradient-to-br from-synthesis-blue/10 to-neutral-50 dark:from-synthesis-blue/5 dark:to-neutral-900 flex items-center justify-center">
    <div className="text-center space-y-8 max-w-4xl mx-auto px-4">
      <div className="flex items-center justify-center space-x-4 mb-8">
        <span className="text-6xl">🏭</span>
        <h1 className="text-h1 text-synthesis-blue">LeadFactory</h1>
      </div>
      
      <p className="text-xl text-neutral max-w-2xl mx-auto">
        Streamline your lead generation process with our comprehensive platform designed for modern sales and marketing teams.
      </p>
      
      <div className="flex flex-col sm:flex-row gap-4 justify-center">
        <a href="/login" className="btn-primary">
          Get Started
        </a>
        <a href="/dashboard" className="btn-secondary">
          View Dashboard
        </a>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mt-16">
        <div className="card text-center">
          <div className="text-4xl mb-4">🎯</div>
          <h3 className="text-h3 mb-2">Lead Management</h3>
          <p className="text-neutral">Track and nurture leads through your sales pipeline with powerful automation.</p>
        </div>
        <div className="card text-center">
          <div className="text-4xl mb-4">📊</div>
          <h3 className="text-h3 mb-2">Analytics</h3>
          <p className="text-neutral">Get deep insights into your lead generation performance and ROI.</p>
        </div>
        <div className="card text-center">
          <div className="text-4xl mb-4">🚀</div>
          <h3 className="text-h3 mb-2">Campaigns</h3>
          <p className="text-neutral">Create and manage multi-channel marketing campaigns that drive results.</p>
        </div>
      </div>
    </div>
  </div>
)

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public routes */}
        <Route path="/" element={<PublicShell />}>
          <Route index element={<HomePage />} />
          <Route path="login" element={<LoginPage />} />
        </Route>

        {/* Protected authenticated routes */}
        <Route path="/dashboard" element={<AuthenticatedShell />}>
          <Route index element={<DashboardPage />} />
        </Route>

        <Route path="/leads" element={<AuthenticatedShell />}>
          <Route index element={<LeadsPage />} />
        </Route>

        <Route path="/campaigns" element={<AuthenticatedShell />}>
          <Route index element={<CampaignsPage />} />
        </Route>

        <Route path="/analytics" element={<AuthenticatedShell />}>
          <Route index element={<AnalyticsPage />} />
        </Route>

        <Route path="/reports" element={<AuthenticatedShell />}>
          <Route index element={<ReportsPage />} />
        </Route>

        {/* Admin routes */}
        <Route path="/admin" element={<AdminShell />}>
          <Route index element={<AdminPage />} />
        </Route>

        {/* Fallback routes */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App