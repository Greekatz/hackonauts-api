import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { fetchWithFallback, postWithFallback } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from '@/hooks/use-toast';
import { TableSkeleton } from '@/components/SkeletonLoader';
import {
  Key,
  Plus,
  Copy,
  Trash2,
  Clock,
  CheckCircle,
  XCircle,
  Eye,
  EyeOff,
  AlertTriangle,
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';

interface ApiKey {
  key: string;
  name: string;
  created_at: string;
  last_used: string | null;
  is_active: boolean;
}

export default function ApiKeys() {
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [newKeyName, setNewKeyName] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [newlyCreatedKey, setNewlyCreatedKey] = useState<string | null>(null);
  const [showKey, setShowKey] = useState<Record<string, boolean>>({});
  const [dialogOpen, setDialogOpen] = useState(false);

  const loadApiKeys = async () => {
    const data = await fetchWithFallback('/api-keys', []);
    setApiKeys(data);
    setLoading(false);
  };

  useEffect(() => {
    loadApiKeys();
  }, []);

  const handleCreateKey = async () => {
    if (!newKeyName.trim()) {
      toast({
        title: 'Name required',
        description: 'Please enter a name for the API key',
        variant: 'destructive',
      });
      return;
    }

    setIsCreating(true);

    try {
      const result = await postWithFallback('/api-keys', { name: newKeyName }, null);

      if (result && result.key) {
        setNewlyCreatedKey(result.key);
        toast({
          title: 'API Key Created',
          description: 'Your new API key has been created. Copy it now - it won\'t be shown again!',
        });
        setNewKeyName('');
        loadApiKeys();
      } else {
        toast({
          title: 'Failed to create key',
          description: 'Could not create API key. You may have reached the maximum limit.',
          variant: 'destructive',
        });
      }
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to create API key',
        variant: 'destructive',
      });
    } finally {
      setIsCreating(false);
    }
  };

  const handleCopyKey = (key: string) => {
    navigator.clipboard.writeText(key);
    toast({
      title: 'Copied!',
      description: 'API key copied to clipboard',
    });
  };

  const handleRevokeKey = async (keyPrefix: string, keyName: string) => {
    try {
      await fetchWithFallback(`/api-keys/${keyPrefix}`, null, {
        method: 'DELETE',
      });
      toast({
        title: 'Key Revoked',
        description: `API key "${keyName}" has been revoked`,
      });
      loadApiKeys();
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to revoke API key',
        variant: 'destructive',
      });
    }
  };

  const handleDeleteKey = async (keyPrefix: string, keyName: string) => {
    try {
      await fetchWithFallback(`/api-keys/${keyPrefix}/delete`, null, {
        method: 'DELETE',
      });
      toast({
        title: 'Key Deleted',
        description: `API key "${keyName}" has been permanently deleted`,
      });
      loadApiKeys();
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to delete API key',
        variant: 'destructive',
      });
    }
  };

  const maskKey = (key: string) => {
    if (key.length <= 12) return key;
    return `${key.slice(0, 8)}...${key.slice(-4)}`;
  };

  const getKeyPrefix = (key: string) => {
    return key.slice(0, 12);
  };

  if (loading) return <TableSkeleton />;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="space-y-6"
    >
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">API Keys</h1>
          <p className="text-muted-foreground">Manage API keys for SDK and API access</p>
        </div>

        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger asChild>
            <Button className="gap-2">
              <Plus className="h-4 w-4" />
              Create API Key
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create New API Key</DialogTitle>
              <DialogDescription>
                Create a new API key for SDK or API access. You can have up to 3 active keys.
              </DialogDescription>
            </DialogHeader>

            {newlyCreatedKey ? (
              <div className="space-y-4">
                <div className="p-4 bg-green-500/10 border border-green-500/20 rounded-lg">
                  <div className="flex items-center gap-2 text-green-600 mb-2">
                    <CheckCircle className="h-5 w-5" />
                    <span className="font-medium">API Key Created!</span>
                  </div>
                  <p className="text-sm text-muted-foreground mb-3">
                    Copy this key now. For security reasons, it won't be shown again.
                  </p>
                  <div className="flex items-center gap-2">
                    <code className="flex-1 p-3 bg-muted rounded font-mono text-sm break-all">
                      {newlyCreatedKey}
                    </code>
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => handleCopyKey(newlyCreatedKey)}
                    >
                      <Copy className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
                <DialogFooter>
                  <Button onClick={() => {
                    setNewlyCreatedKey(null);
                    setDialogOpen(false);
                  }}>
                    Done
                  </Button>
                </DialogFooter>
              </div>
            ) : (
              <>
                <div className="space-y-4 py-4">
                  <div className="space-y-2">
                    <Label htmlFor="key-name">Key Name</Label>
                    <Input
                      id="key-name"
                      placeholder="e.g., Production Server, Development"
                      value={newKeyName}
                      onChange={(e) => setNewKeyName(e.target.value)}
                    />
                    <p className="text-xs text-muted-foreground">
                      A descriptive name to help you identify this key
                    </p>
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setDialogOpen(false)}>
                    Cancel
                  </Button>
                  <Button onClick={handleCreateKey} disabled={isCreating}>
                    {isCreating ? 'Creating...' : 'Create Key'}
                  </Button>
                </DialogFooter>
              </>
            )}
          </DialogContent>
        </Dialog>
      </div>

      {/* Info Card */}
      <Card className="p-4 bg-blue-500/10 border-blue-500/20">
        <div className="flex items-start gap-3">
          <Key className="h-5 w-5 text-blue-500 mt-0.5" />
          <div>
            <h3 className="font-medium text-blue-600">Using API Keys</h3>
            <p className="text-sm text-muted-foreground mt-1">
              Include your API key in the <code className="px-1 py-0.5 bg-muted rounded">X-API-Key</code> header
              when making requests to the SRA API or using the SDK.
            </p>
            <pre className="mt-2 p-2 bg-muted rounded text-xs overflow-x-auto">
              {`curl -H "X-API-Key: sra_your_key_here" https://api.sra.dev/status`}
            </pre>
          </div>
        </div>
      </Card>

      {/* API Keys List */}
      {apiKeys.length === 0 ? (
        <Card className="p-12 text-center">
          <div className="flex flex-col items-center gap-4">
            <div className="p-4 rounded-full bg-muted">
              <Key className="h-12 w-12 text-muted-foreground" />
            </div>
            <h2 className="text-2xl font-semibold">No API Keys</h2>
            <p className="text-muted-foreground max-w-md">
              Create an API key to start using the SRA SDK or make direct API calls.
            </p>
            <Button onClick={() => setDialogOpen(true)} className="gap-2">
              <Plus className="h-4 w-4" />
              Create Your First Key
            </Button>
          </div>
        </Card>
      ) : (
        <div className="space-y-4">
          {apiKeys.map((apiKey, index) => (
            <motion.div
              key={apiKey.key}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.05 }}
            >
              <Card className="p-6">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-4 flex-1">
                    <div className={`p-3 rounded-lg ${apiKey.is_active ? 'bg-green-500/10' : 'bg-red-500/10'}`}>
                      <Key className={`h-6 w-6 ${apiKey.is_active ? 'text-green-500' : 'text-red-500'}`} />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <h3 className="text-xl font-semibold">{apiKey.name}</h3>
                        <Badge variant={apiKey.is_active ? 'default' : 'destructive'}>
                          {apiKey.is_active ? 'Active' : 'Revoked'}
                        </Badge>
                      </div>

                      <div className="flex items-center gap-2 mb-3">
                        <code className="px-2 py-1 bg-muted rounded font-mono text-sm">
                          {showKey[apiKey.key] ? apiKey.key : maskKey(apiKey.key)}
                        </code>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={() => setShowKey(prev => ({ ...prev, [apiKey.key]: !prev[apiKey.key] }))}
                        >
                          {showKey[apiKey.key] ? (
                            <EyeOff className="h-4 w-4" />
                          ) : (
                            <Eye className="h-4 w-4" />
                          )}
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={() => handleCopyKey(apiKey.key)}
                        >
                          <Copy className="h-4 w-4" />
                        </Button>
                      </div>

                      <div className="flex items-center gap-4 text-sm text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <Clock className="h-4 w-4" />
                          Created: {new Date(apiKey.created_at).toLocaleDateString()}
                        </span>
                        {apiKey.last_used && (
                          <span className="flex items-center gap-1">
                            <CheckCircle className="h-4 w-4" />
                            Last used: {new Date(apiKey.last_used).toLocaleDateString()}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    {apiKey.is_active && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleRevokeKey(getKeyPrefix(apiKey.key), apiKey.name)}
                        className="gap-2 text-orange-600 hover:text-orange-700"
                      >
                        <XCircle className="h-4 w-4" />
                        Revoke
                      </Button>
                    )}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleDeleteKey(getKeyPrefix(apiKey.key), apiKey.name)}
                      className="gap-2 text-red-600 hover:text-red-700"
                    >
                      <Trash2 className="h-4 w-4" />
                      Delete
                    </Button>
                  </div>
                </div>
              </Card>
            </motion.div>
          ))}
        </div>
      )}

      {/* Warning */}
      <Card className="p-4 bg-yellow-500/10 border-yellow-500/20">
        <div className="flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-yellow-600 mt-0.5" />
          <div>
            <h3 className="font-medium text-yellow-600">Security Notice</h3>
            <p className="text-sm text-muted-foreground mt-1">
              Keep your API keys secure. Never commit them to version control or share them publicly.
              If a key is compromised, revoke it immediately and create a new one.
            </p>
          </div>
        </div>
      </Card>
    </motion.div>
  );
}
