import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { fetchWithFallback } from '@/lib/api';
import { mockReports } from '@/lib/mockData';
import { TableSkeleton } from '@/components/SkeletonLoader';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { toast } from '@/hooks/use-toast';
import { Download, FileText, User, Calendar } from 'lucide-react';

export default function Reports() {
  const [reports, setReports] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadReports = async () => {
      const data = await fetchWithFallback('/reports', mockReports);
      setReports(data);
      setLoading(false);
    };
    loadReports();
  }, []);

  const handleDownload = (id: string, title: string) => {
    toast({
      title: 'Downloading Report',
      description: `${title} will be downloaded shortly...`,
    });
  };

  if (loading) return <TableSkeleton />;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="space-y-6"
    >
      <div>
        <h1 className="text-3xl font-bold">Reports</h1>
        <p className="text-muted-foreground">Post-mortems and incident analysis</p>
      </div>

      <div className="grid gap-4">
        {reports.map((report, index) => (
          <motion.div
            key={report.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.05 }}
          >
            <Card className="p-6">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <FileText className="h-5 w-5 text-muted-foreground" />
                    <h3 className="text-xl font-semibold">{report.title}</h3>
                    <Badge variant={report.status === 'published' ? 'default' : 'outline'}>
                      {report.status}
                    </Badge>
                  </div>

                  <div className="flex items-center gap-6 text-sm text-muted-foreground mt-3">
                    <div className="flex items-center gap-2">
                      <Calendar className="h-4 w-4" />
                      {new Date(report.date).toLocaleDateString()}
                    </div>
                    <div className="flex items-center gap-2">
                      <User className="h-4 w-4" />
                      {report.author}
                    </div>
                    {report.incident && (
                      <div>Related: {report.incident}</div>
                    )}
                  </div>
                </div>

                {report.status === 'published' && (
                  <Button
                    onClick={() => handleDownload(report.id, report.title)}
                    variant="outline"
                    className="gap-2"
                  >
                    <Download className="h-4 w-4" />
                    Download
                  </Button>
                )}
              </div>
            </Card>
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
}
