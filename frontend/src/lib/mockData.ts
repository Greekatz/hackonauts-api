// Mock data for demo fallback

export const mockIncidents = [
  {
    id: 'INC-001',
    title: 'Database connection pool exhausted',
    severity: 'sev1',
    status: 'open',
    service: 'payment-api',
    created: '2025-01-15T10:30:00Z',
    updated: '2025-01-15T10:45:00Z',
    assignee: 'SRE Team',
    description: 'Payment API experiencing connection timeouts due to exhausted DB pool',
    impact: 'Payment processing degraded for 15% of transactions',
    affectedUsers: 1247,
  },
  {
    id: 'INC-002',
    title: 'High memory usage on app servers',
    severity: 'sev2',
    status: 'acknowledged',
    service: 'web-app',
    created: '2025-01-15T09:15:00Z',
    updated: '2025-01-15T10:30:00Z',
    assignee: 'Platform Team',
    description: 'Memory usage above 85% on 3 application servers',
    impact: 'Potential service degradation if memory leak continues',
    affectedUsers: 0,
  },
  {
    id: 'INC-003',
    title: 'Elevated error rate in checkout flow',
    severity: 'sev2',
    status: 'open',
    service: 'checkout-service',
    created: '2025-01-15T11:00:00Z',
    updated: '2025-01-15T11:15:00Z',
    assignee: 'Commerce Team',
    description: 'Error rate increased from 0.1% to 2.5% in checkout completion',
    impact: 'Users unable to complete purchases',
    affectedUsers: 523,
  },
  {
    id: 'INC-004',
    title: 'Certificate expiration warning',
    severity: 'sev3',
    status: 'acknowledged',
    service: 'api-gateway',
    created: '2025-01-14T08:00:00Z',
    updated: '2025-01-15T09:00:00Z',
    assignee: 'Security Team',
    description: 'SSL certificate expires in 7 days',
    impact: 'No current impact, requires renewal',
    affectedUsers: 0,
  },
  {
    id: 'INC-005',
    title: 'Redis cluster node failure',
    severity: 'sev1',
    status: 'resolved',
    service: 'cache-layer',
    created: '2025-01-14T14:30:00Z',
    updated: '2025-01-14T15:45:00Z',
    resolvedAt: '2025-01-14T15:45:00Z',
    assignee: 'Infrastructure Team',
    description: 'Primary Redis node failed, automatic failover triggered',
    impact: 'Brief cache unavailability during failover',
    affectedUsers: 2341,
  },
];

export const mockIncidentDetail = {
  id: 'INC-001',
  title: 'Database connection pool exhausted',
  severity: 'sev1',
  status: 'open',
  service: 'payment-api',
  created: '2025-01-15T10:30:00Z',
  updated: '2025-01-15T10:45:00Z',
  assignee: 'SRE Team',
  description: 'Payment API experiencing connection timeouts due to exhausted DB pool',
  impact: 'Payment processing degraded for 15% of transactions',
  affectedUsers: 1247,
  summary: 'The payment API service is experiencing database connection pool exhaustion, leading to timeouts and failed transactions. Initial investigation shows a spike in concurrent database connections starting at 10:25 UTC.',
  rca: `**Root Cause Analysis:**

1. **Trigger Event**: Sudden 3x increase in payment volume at 10:25 UTC
2. **Contributing Factors**:
   - Connection pool sized for average load (50 connections)
   - Long-running transactions holding connections
   - No connection timeout configured on application side
3. **Impact Path**: High connection count → Pool exhaustion → New requests timeout → Failed payments
4. **Why It Wasn't Caught**: Load testing scenarios didn't include sustained high-volume periods`,
  plans: [
    {
      id: 'RB-001',
      name: 'Increase DB Connection Pool',
      status: 'ready',
      steps: ['Scale connection pool to 150', 'Add connection timeout (30s)', 'Monitor for 5 minutes'],
    },
    {
      id: 'RB-002',
      name: 'Scale Payment API Horizontally',
      status: 'ready',
      steps: ['Add 2 additional API instances', 'Update load balancer', 'Verify traffic distribution'],
    },
  ],
  logs: [
    { timestamp: '10:45:23', level: 'ERROR', message: 'Connection timeout after 30000ms' },
    { timestamp: '10:44:58', level: 'WARN', message: 'Connection pool at 98% capacity' },
    { timestamp: '10:44:12', level: 'ERROR', message: 'Failed to acquire connection from pool' },
    { timestamp: '10:43:45', level: 'WARN', message: 'High connection wait time: 2500ms' },
  ],
  metrics: {
    errorRate: [
      { time: '10:30', value: 0.2 },
      { time: '10:35', value: 2.1 },
      { time: '10:40', value: 5.8 },
      { time: '10:45', value: 12.3 },
    ],
    latency: [
      { time: '10:30', value: 145 },
      { time: '10:35', value: 380 },
      { time: '10:40', value: 1250 },
      { time: '10:45', value: 2890 },
    ],
    connections: [
      { time: '10:30', value: 42 },
      { time: '10:35', value: 48 },
      { time: '10:40', value: 50 },
      { time: '10:45', value: 50 },
    ],
  },
  timeline: [
    { time: '10:25', event: 'Traffic spike detected', type: 'info' },
    { time: '10:30', event: 'Incident created automatically', type: 'warning' },
    { time: '10:32', event: 'Alert sent to SRE team', type: 'info' },
    { time: '10:35', event: 'Connection pool at capacity', type: 'error' },
    { time: '10:40', event: 'Error rate exceeds 10%', type: 'critical' },
    { time: '10:45', event: 'Runbooks identified', type: 'info' },
  ],
};

export const mockAnalytics = {
  mtta: { current: 8.5, previous: 12.3, trend: 'down' },
  mttr: { current: 42.3, previous: 58.7, trend: 'down' },
  incidentTrends: [
    { date: '2025-01-08', sev1: 2, sev2: 5, sev3: 8 },
    { date: '2025-01-09', sev1: 1, sev2: 7, sev3: 6 },
    { date: '2025-01-10', sev1: 3, sev2: 4, sev3: 9 },
    { date: '2025-01-11', sev1: 0, sev2: 6, sev3: 7 },
    { date: '2025-01-12', sev1: 2, sev2: 3, sev3: 5 },
    { date: '2025-01-13', sev1: 1, sev2: 5, sev3: 8 },
    { date: '2025-01-14', sev1: 2, sev2: 4, sev3: 6 },
  ],
  errorRates: [
    { service: 'payment-api', rate: 2.3 },
    { service: 'checkout-service', rate: 1.8 },
    { service: 'auth-service', rate: 0.4 },
    { service: 'web-app', rate: 0.9 },
    { service: 'api-gateway', rate: 0.2 },
  ],
  latencyP95: [
    { hour: '00:00', value: 156 },
    { hour: '04:00', value: 142 },
    { hour: '08:00', value: 298 },
    { hour: '12:00', value: 412 },
    { hour: '16:00', value: 387 },
    { hour: '20:00', value: 223 },
  ],
};

export const mockRunbooks = [
  {
    id: 'RB-001',
    name: 'Increase DB Connection Pool',
    category: 'database',
    description: 'Scale database connection pool and add timeouts',
    lastRun: '2025-01-10T14:30:00Z',
    successRate: 95,
    avgDuration: '3m 45s',
  },
  {
    id: 'RB-002',
    name: 'Scale API Horizontally',
    category: 'compute',
    description: 'Add additional API instances to handle load',
    lastRun: '2025-01-12T09:15:00Z',
    successRate: 98,
    avgDuration: '5m 12s',
  },
  {
    id: 'RB-003',
    name: 'Restart Failing Service',
    category: 'service',
    description: 'Graceful restart of service with health checks',
    lastRun: '2025-01-14T16:20:00Z',
    successRate: 92,
    avgDuration: '2m 30s',
  },
  {
    id: 'RB-004',
    name: 'Clear Cache Cluster',
    category: 'cache',
    description: 'Flush Redis cache and verify connectivity',
    lastRun: '2025-01-09T11:45:00Z',
    successRate: 100,
    avgDuration: '1m 15s',
  },
];

export const mockReports = [
  {
    id: 'RPT-001',
    title: 'Redis Cluster Node Failure - Post-Mortem',
    incident: 'INC-005',
    date: '2025-01-14',
    status: 'published',
    author: 'Infrastructure Team',
  },
  {
    id: 'RPT-002',
    title: 'Q4 2024 Incident Review',
    date: '2025-01-05',
    status: 'published',
    author: 'SRE Leadership',
  },
  {
    id: 'RPT-003',
    title: 'Payment API Degradation Analysis',
    incident: 'INC-001',
    date: '2025-01-15',
    status: 'draft',
    author: 'SRE Team',
  },
];

export const mockIntegrations = [
  { id: 'slack', name: 'Slack', status: 'connected', lastSync: '2 min ago' },
  { id: 'servicenow', name: 'ServiceNow', status: 'connected', lastSync: '5 min ago' },
  { id: 'pagerduty', name: 'PagerDuty', status: 'connected', lastSync: '1 min ago' },
  { id: 'datadog', name: 'Datadog', status: 'connected', lastSync: '30 sec ago' },
  { id: 'jira', name: 'Jira', status: 'disconnected', lastSync: 'Never' },
];

export const mockAgentState = {
  status: 'active',
  lastRun: '2025-01-15T11:45:23Z',
  loopCount: 247,
  currentTask: 'Monitoring incident INC-001',
  health: 'healthy',
  lastPayload: {
    action: 'analyze_incident',
    incident_id: 'INC-001',
    metrics_collected: true,
    recommendations: ['scale_horizontally', 'increase_connection_pool'],
    confidence: 0.87,
  },
};
