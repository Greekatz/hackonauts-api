import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
import {
  AlertCircle,
  BarChart3,
  BookOpen,
  FileText,
  Settings,
  Plug,
  Bug,
} from 'lucide-react';

const commands = [
  { id: 'incidents', label: 'Go to Incidents', icon: AlertCircle, path: '/incidents', shortcut: 'g i' },
  { id: 'analytics', label: 'Go to Analytics', icon: BarChart3, path: '/analytics', shortcut: 'g a' },
  { id: 'runbooks', label: 'Go to Runbooks', icon: BookOpen, path: '/runbooks', shortcut: 'g r' },
  { id: 'reports', label: 'Go to Reports', icon: FileText, path: '/reports', shortcut: 'g p' },
  { id: 'config', label: 'Go to Config', icon: Settings, path: '/config', shortcut: 'g c' },
  { id: 'integrations', label: 'Go to Integrations', icon: Plug, path: '/integrations', shortcut: 'g t' },
  { id: 'debug', label: 'Go to Debug', icon: Bug, path: '/debug', shortcut: 'g d' },
];

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === '?' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((open) => !open);
      }

      // Navigation shortcuts
      if (e.key === 'g' && !open) {
        const handleNextKey = (nextE: KeyboardEvent) => {
          const command = commands.find((cmd) => cmd.shortcut === `g ${nextE.key}`);
          if (command) {
            navigate(command.path);
          }
          window.removeEventListener('keydown', handleNextKey);
        };
        window.addEventListener('keydown', handleNextKey);
      }
    };

    document.addEventListener('keydown', down);
    return () => document.removeEventListener('keydown', down);
  }, [navigate, open]);

  const runCommand = (path: string) => {
    setOpen(false);
    navigate(path);
  };

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder="Type a command or search..." />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>
        <CommandGroup heading="Navigation">
          {commands.map((command) => (
            <CommandItem
              key={command.id}
              onSelect={() => runCommand(command.path)}
              className="gap-2"
            >
              <command.icon className="h-4 w-4" />
              <span>{command.label}</span>
              <kbd className="ml-auto text-xs bg-muted px-2 py-1 rounded">
                {command.shortcut}
              </kbd>
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
