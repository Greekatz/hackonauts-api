import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Send } from "lucide-react";

interface Message {
  id: string;
  text: string;
  sender: "user" | "other";
  timestamp: Date;
}

const ChatBox = () => {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "1",
      text: "Hey! How are you?",
      sender: "other",
      timestamp: new Date(Date.now() - 3600000),
    },
    {
      id: "2",
      text: "I'm doing great! Just working on this cool chat interface.",
      sender: "user",
      timestamp: new Date(Date.now() - 3300000),
    },
    {
      id: "3",
      text: "That sounds exciting! What features are you adding?",
      sender: "other",
      timestamp: new Date(Date.now() - 3000000),
    },
  ]);
  const [inputValue, setInputValue] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = () => {
    if (inputValue.trim()) {
      const newMessage: Message = {
        id: Date.now().toString(),
        text: inputValue,
        sender: "user",
        timestamp: new Date(),
      };
      setMessages([...messages, newMessage]);
      setInputValue("");
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  return (
    <div className="flex flex-col h-[600px] max-w-2xl mx-auto bg-card rounded-2xl shadow-lg border border-border overflow-hidden">
      {/* Header */}
      <div className="bg-primary px-6 py-4 border-b border-border/50">
        <h2 className="text-lg font-semibold text-primary-foreground">Chat</h2>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4 bg-background/50">
        {messages.map((message, index) => (
          <div
            key={message.id}
            className={`flex ${message.sender === "user" ? "justify-end" : "justify-start"} animate-in fade-in slide-in-from-bottom-2`}
            style={{ animationDelay: `${index * 50}ms` }}
          >
            <div
              className={`max-w-[75%] rounded-2xl px-4 py-3 transition-all hover:scale-[1.02] ${
                message.sender === "user"
                  ? "bg-chat-sent text-chat-sent-foreground rounded-br-sm"
                  : "bg-chat-received text-chat-received-foreground rounded-bl-sm"
              }`}
            >
              <p className="text-sm leading-relaxed">{message.text}</p>
              <span className="text-xs opacity-70 mt-1 block">
                {formatTime(message.timestamp)}
              </span>
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-border bg-card p-4">
        <div className="flex gap-2">
          <Input
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Type a message..."
            className="flex-1 rounded-xl bg-background border-border focus-visible:ring-primary"
          />
          <Button
            onClick={handleSend}
            size="icon"
            className="rounded-xl bg-primary hover:bg-primary/90 transition-all hover:scale-105"
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
};

export default ChatBox;