import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import {
  Shield,
  Zap,
  Activity,
  Brain,
  Bell,
  GitBranch,
  ArrowRight,
  CheckCircle,
  Clock,
  Users,
  BarChart3,
  Slack,
  Terminal,
} from 'lucide-react';

const features = [
  {
    icon: Brain,
    title: 'AI-Powered Detection',
    description: 'IBM watsonx continuously analyzes your logs and metrics every 5 minutes to detect anomalies before they impact users.',
  },
  {
    icon: Zap,
    title: 'Instant Root Cause Analysis',
    description: 'Get detailed RCA reports with contributing factors, evidence, and actionable recommendations within seconds.',
  },
  {
    icon: Shield,
    title: 'One-Click Auto-Healing',
    description: 'Execute recommended fixes with a single click. Restart services, scale replicas, flush caches, and more.',
  },
  {
    icon: Bell,
    title: 'Slack Integration',
    description: 'Receive instant alerts in Slack with interactive buttons to acknowledge, escalate, or auto-heal incidents.',
  },
  {
    icon: GitBranch,
    title: 'Runbook Automation',
    description: 'Pre-built runbooks for common issues. Execute recovery plans automatically or with approval.',
  },
  {
    icon: BarChart3,
    title: 'Analytics Dashboard',
    description: 'Track MTTA, MTTR, incident trends, and service health metrics in a beautiful dashboard.',
  },
];

const stats = [
  { value: '< 5min', label: 'Detection Time' },
  { value: '90%', label: 'Faster Resolution' },
  { value: '24/7', label: 'Monitoring' },
  { value: '1-Click', label: 'Auto-Healing' },
];

const workflow = [
  {
    step: '01',
    title: 'Ingest',
    description: 'Send logs and metrics via SDK or API',
    icon: Terminal,
  },
  {
    step: '02',
    title: 'Analyze',
    description: 'AI detects anomalies and identifies root cause',
    icon: Brain,
  },
  {
    step: '03',
    title: 'Alert',
    description: 'Get notified via Slack with RCA details',
    icon: Slack,
  },
  {
    step: '04',
    title: 'Heal',
    description: 'Execute fixes automatically or with one click',
    icon: Zap,
  },
];

export default function Landing() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-background">
      {/* Navigation */}
      <nav className="fixed top-0 w-full z-50 bg-background/80 backdrop-blur-sm border-b">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-primary flex items-center justify-center">
              <Shield className="h-5 w-5 text-primary-foreground" />
            </div>
            <span className="font-bold text-xl">SRA</span>
          </div>
          <div className="flex items-center gap-4">
            <Button variant="ghost" onClick={() => navigate('/login')}>
              Sign In
            </Button>
            <Button onClick={() => navigate('/login')}>
              Get Started
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="pt-32 pb-20 px-6">
        <div className="max-w-7xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-center max-w-4xl mx-auto"
          >
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 text-primary text-sm font-medium mb-8">
              <Zap className="h-4 w-4" />
              Powered by IBM watsonx
            </div>
            <h1 className="text-5xl md:text-7xl font-bold tracking-tight mb-6">
              Incident Response
              <span className="text-primary"> on Autopilot</span>
            </h1>
            <p className="text-xl text-muted-foreground mb-8 max-w-2xl mx-auto">
              AI-powered system reliability platform that detects anomalies, performs root cause analysis,
              and executes automated remediation — all in real-time.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Button size="lg" onClick={() => navigate('/login')} className="text-lg px-8">
                Start Free Trial
                <ArrowRight className="ml-2 h-5 w-5" />
              </Button>
              <Button size="lg" variant="outline" className="text-lg px-8">
                View Demo
              </Button>
            </div>
          </motion.div>

          {/* Stats */}
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="grid grid-cols-2 md:grid-cols-4 gap-8 mt-20"
          >
            {stats.map((stat, index) => (
              <div key={index} className="text-center">
                <div className="text-4xl font-bold text-primary">{stat.value}</div>
                <div className="text-muted-foreground mt-1">{stat.label}</div>
              </div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* Dashboard Preview */}
      <section className="py-20 px-6 bg-muted/30">
        <div className="max-w-7xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="relative"
          >
            <div className="absolute inset-0 bg-gradient-to-t from-background to-transparent z-10 pointer-events-none" />
            <Card className="overflow-hidden border-2 shadow-2xl">
              <div className="bg-muted/50 px-4 py-3 border-b flex items-center gap-2">
                <div className="flex gap-1.5">
                  <div className="h-3 w-3 rounded-full bg-red-500" />
                  <div className="h-3 w-3 rounded-full bg-yellow-500" />
                  <div className="h-3 w-3 rounded-full bg-green-500" />
                </div>
                <span className="text-sm text-muted-foreground ml-2">SRA Dashboard</span>
              </div>
              <div className="p-6 bg-background min-h-[400px] flex items-center justify-center">
                <div className="grid grid-cols-3 gap-6 w-full max-w-4xl">
                  {/* Mock incident cards */}
                  {[
                    { title: 'Database Connection Pool Exhausted', severity: 'critical', status: 'open' },
                    { title: 'High Memory Usage on API Servers', severity: 'high', status: 'acknowledged' },
                    { title: 'Elevated Error Rate in Checkout', severity: 'medium', status: 'investigating' },
                  ].map((incident, i) => (
                    <motion.div
                      key={i}
                      initial={{ opacity: 0, scale: 0.9 }}
                      whileInView={{ opacity: 1, scale: 1 }}
                      viewport={{ once: true }}
                      transition={{ delay: i * 0.1 }}
                    >
                      <Card className="p-4">
                        <div className="flex items-start justify-between mb-3">
                          <span className={`px-2 py-1 rounded text-xs font-medium ${
                            incident.severity === 'critical' ? 'bg-red-500/20 text-red-500' :
                            incident.severity === 'high' ? 'bg-orange-500/20 text-orange-500' :
                            'bg-yellow-500/20 text-yellow-500'
                          }`}>
                            {incident.severity.toUpperCase()}
                          </span>
                          <span className="text-xs text-muted-foreground">{incident.status}</span>
                        </div>
                        <h4 className="font-medium text-sm">{incident.title}</h4>
                        <div className="flex items-center gap-2 mt-3 text-xs text-muted-foreground">
                          <Clock className="h-3 w-3" />
                          <span>5 min ago</span>
                        </div>
                      </Card>
                    </motion.div>
                  ))}
                </div>
              </div>
            </Card>
          </motion.div>
        </div>
      </section>

      {/* How It Works */}
      <section className="py-20 px-6">
        <div className="max-w-7xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-4xl font-bold mb-4">How It Works</h2>
            <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
              From detection to resolution in minutes, not hours
            </p>
          </motion.div>

          <div className="relative">
            {/* Connecting line behind cards */}
            <div className="hidden md:block absolute top-24 left-[10%] right-[10%] h-0.5 bg-gradient-to-r from-transparent via-primary/30 to-transparent" />

            <div className="grid md:grid-cols-4 gap-8">
              {workflow.map((item, index) => (
                <motion.div
                  key={index}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: index * 0.1 }}
                  className="text-center"
                >
                  <div className="text-5xl font-bold text-primary/20 mb-3">{item.step}</div>
                  <div className="h-14 w-14 rounded-xl bg-background dark:bg-zinc-950 border border-primary/30 flex items-center justify-center mb-4 mx-auto relative z-20 shadow-lg shadow-primary/10">
                    <item.icon className="h-7 w-7 text-primary" />
                  </div>
                  <h3 className="text-xl font-semibold mb-2">{item.title}</h3>
                  <p className="text-muted-foreground text-sm">{item.description}</p>
                </motion.div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Features Grid */}
      <section className="py-20 px-6 bg-muted/30">
        <div className="max-w-7xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-4xl font-bold mb-4">Everything You Need</h2>
            <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
              A complete platform for incident detection, analysis, and automated remediation
            </p>
          </motion.div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((feature, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: index * 0.05 }}
              >
                <Card className="p-6 h-full hover:shadow-lg transition-shadow">
                  <div className="h-12 w-12 rounded-xl bg-primary/10 flex items-center justify-center mb-4">
                    <feature.icon className="h-6 w-6 text-primary" />
                  </div>
                  <h3 className="text-xl font-semibold mb-2">{feature.title}</h3>
                  <p className="text-muted-foreground">{feature.description}</p>
                </Card>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Integration Section */}
      <section className="py-20 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
            >
              <h2 className="text-4xl font-bold mb-6">
                Integrate in Minutes
              </h2>
              <p className="text-xl text-muted-foreground mb-8">
                Get started with just a few lines of code. Our Python SDK makes it easy to send logs and metrics from any application.
              </p>
              <ul className="space-y-4">
                {[
                  'Simple pip install',
                  'Drop-in logging handler',
                  'Automatic system metrics',
                  'Works with existing logging',
                ].map((item, i) => (
                  <li key={i} className="flex items-center gap-3">
                    <CheckCircle className="h-5 w-5 text-primary" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, x: 20 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
            >
              <Card className="overflow-hidden">
                <div className="bg-zinc-900 px-4 py-3 border-b border-zinc-800 flex items-center gap-2">
                  <Terminal className="h-4 w-4 text-zinc-400" />
                  <span className="text-sm text-zinc-400">Python</span>
                </div>
                <pre className="p-6 bg-zinc-950 text-sm overflow-x-auto">
                  <code className="text-zinc-300">
{`from sra_sdk import SRALogger

logger = SRALogger(
    api_key="sra_...",
    endpoint="https://your-sra.com",
    service="my-api"
)

# That's it! Now your logs are monitored
logger.info("Application started")
logger.error("Database connection failed")`}
                  </code>
                </pre>
              </Card>
            </motion.div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 px-6">
        <div className="max-w-4xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <Card className="p-12 text-center bg-gradient-to-br from-primary/10 via-background to-primary/5 border-primary/20">
              <h2 className="text-4xl font-bold mb-4">
                Ready to Automate Your Incident Response?
              </h2>
              <p className="text-xl text-muted-foreground mb-8 max-w-2xl mx-auto">
                Join teams who have reduced their MTTR by 90% with AI-powered incident management.
              </p>
              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <Button size="lg" onClick={() => navigate('/login')} className="text-lg px-8">
                  Get Started Free
                  <ArrowRight className="ml-2 h-5 w-5" />
                </Button>
                <Button size="lg" variant="outline" className="text-lg px-8">
                  Schedule Demo
                </Button>
              </div>
            </Card>
          </motion.div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t py-12 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <div className="h-8 w-8 rounded-lg bg-primary flex items-center justify-center">
                <Shield className="h-5 w-5 text-primary-foreground" />
              </div>
              <span className="font-bold">SRA</span>
              <span className="text-muted-foreground">System Reliability Assistant</span>
            </div>
            <p className="text-sm text-muted-foreground">
              Powered by IBM watsonx
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
