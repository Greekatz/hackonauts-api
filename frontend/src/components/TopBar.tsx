import { Moon, Sun, Zap, RotateCw } from 'lucide-react';
import { useTheme } from '@/contexts/ThemeContext';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { SidebarTrigger } from '@/components/ui/sidebar';
import { toast } from '@/hooks/use-toast';
import { motion } from 'framer-motion';

export function TopBar() {
  const { theme, toggleTheme } = useTheme();

  const handleTriggerAgent = () => {
    toast({
      title: 'Agent Triggered',
      description: 'Watsonx agent analysis loop initiated...',
    });
  };

  const handleRerunLoop = () => {
    toast({
      title: 'Loop Restarted',
      description: 'Agent re-running analysis with latest data...',
    });
  };

  return (
    <motion.header
      initial={{ y: -20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      className="sticky top-0 z-50 flex h-14 items-center gap-4 border-b bg-card/95 backdrop-blur-sm px-4"
    >
      <SidebarTrigger className="flex-shrink-0" />
      
      <div className="flex items-center gap-2 flex-1">
        <h1 className="text-lg font-semibold">SRA</h1>
        <Badge variant="outline" className="bg-primary/10 text-primary border-primary/20">
          Production
        </Badge>
      </div>

      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={handleTriggerAgent}
          className="gap-2"
        >
          <Zap className="h-4 w-4" />
          <span className="hidden sm:inline">Trigger Agent</span>
        </Button>
        
        <Button
          variant="outline"
          size="sm"
          onClick={handleRerunLoop}
          className="gap-2"
        >
          <RotateCw className="h-4 w-4" />
          <span className="hidden sm:inline">Re-run Loop</span>
        </Button>

        <Button
          variant="ghost"
          size="icon"
          onClick={toggleTheme}
          className="transition-smooth"
        >
          {theme === 'dark' ? (
            <Sun className="h-5 w-5" />
          ) : (
            <Moon className="h-5 w-5" />
          )}
        </Button>
      </div>
    </motion.header>
  );
}
