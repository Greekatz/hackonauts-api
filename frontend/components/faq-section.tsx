"use client"

import type React from "react"
import { useState } from "react"
import { ChevronDown } from "lucide-react"

const faqData = [
  {
    question: "What is Watsonx Resilience Co-Pilot and who is it for?",
    answer:
      "Watsonx Resilience Co-Pilot is an AI-powered bug detection and fault tolerance system designed for development teams who want to catch errors before they impact users. It monitors your frontend and backend systems in real-time, automatically routing notifications to the right team members when issues occur.",
  },
  {
    question: "How does the AI-powered error detection work?",
    answer:
      "Our AI analyzes error patterns, stack traces, and system logs in real-time to identify bugs and vulnerabilities. It learns from your application's behavior to distinguish between critical issues and false alarms, providing intelligent prioritization and suggesting potential fixes based on similar past incidents.",
  },
  {
    question: "What types of errors can Watsonx detect?",
    answer:
      "Watsonx monitors both frontend and backend errors including JavaScript exceptions, API failures, database connectivity issues, performance bottlenecks, memory leaks, and security vulnerabilities. It tracks errors across your entire stack and provides unified visibility into your application's health.",
  },
  {
    question: "How does smart notification routing work?",
    answer:
      "Based on error type, severity, and affected components, Watsonx automatically notifies the right team members through their preferred channels (email, Slack, webhooks). You can configure custom routing rules and escalation paths to ensure critical issues reach the right people immediately.",
  },
  {
    question: "What is fault tolerance management?",
    answer:
      "Our fault tolerance system implements intelligent fallback mechanisms that keep your application running even when errors occur. It can automatically retry failed operations, switch to backup services, and gracefully degrade functionality to maintain user experience while issues are being resolved.",
  },
  {
    question: "Is my application data secure with Watsonx?",
    answer:
      "Absolutely. We use enterprise-grade encryption for all data in transit and at rest. Error logs are sanitized to remove sensitive information, and we offer on-premise deployment options for enterprise customers. Watsonx is SOC 2 compliant and follows industry best practices for data security.",
  },
]

interface FAQItemProps {
  question: string
  answer: string
  isOpen: boolean
  onToggle: () => void
}

const FAQItem = ({ question, answer, isOpen, onToggle }: FAQItemProps) => {
  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault()
    onToggle()
  }
  return (
    <div
      className={`w-full bg-[rgba(231,236,235,0.08)] shadow-[0px_2px_4px_rgba(0,0,0,0.16)] overflow-hidden rounded-[10px] outline outline-1 outline-border outline-offset-[-1px] transition-all duration-500 ease-out cursor-pointer`}
      onClick={handleClick}
    >
      <div className="w-full px-5 py-[18px] pr-4 flex justify-between items-center gap-5 text-left transition-all duration-300 ease-out">
        <div className="flex-1 text-foreground text-base font-medium leading-6 break-words">{question}</div>
        <div className="flex justify-center items-center">
          <ChevronDown
            className={`w-6 h-6 text-muted-foreground-dark transition-all duration-500 ease-out ${isOpen ? "rotate-180 scale-110" : "rotate-0 scale-100"}`}
          />
        </div>
      </div>
      <div
        className={`overflow-hidden transition-all duration-500 ease-out ${isOpen ? "max-h-[500px] opacity-100" : "max-h-0 opacity-0"}`}
        style={{
          transitionProperty: "max-height, opacity, padding",
          transitionTimingFunction: "cubic-bezier(0.4, 0, 0.2, 1)",
        }}
      >
        <div
          className={`px-5 transition-all duration-500 ease-out ${isOpen ? "pb-[18px] pt-2 translate-y-0" : "pb-0 pt-0 -translate-y-2"}`}
        >
          <div className="text-foreground/80 text-sm font-normal leading-6 break-words">{answer}</div>
        </div>
      </div>
    </div>
  )
}

export function FAQSection() {
  const [openItems, setOpenItems] = useState<Set<number>>(new Set())
  const toggleItem = (index: number) => {
    const newOpenItems = new Set(openItems)
    if (newOpenItems.has(index)) {
      newOpenItems.delete(index)
    } else {
      newOpenItems.add(index)
    }
    setOpenItems(newOpenItems)
  }
  return (
    <section className="w-full pt-[66px] pb-20 md:pb-40 px-5 relative flex flex-col justify-center items-center">
      <div className="w-[300px] h-[500px] absolute top-[150px] left-1/2 -translate-x-1/2 origin-top-left rotate-[-33.39deg] bg-primary/10 blur-[100px] z-0" />
      <div className="self-stretch pt-8 pb-8 md:pt-14 md:pb-14 flex flex-col justify-center items-center gap-2 relative z-10">
        <div className="flex flex-col justify-start items-center gap-4">
          <h2 className="w-full max-w-[435px] text-center text-foreground text-4xl font-semibold leading-10 break-words">
            Frequently Asked Questions
          </h2>
          <p className="self-stretch text-center text-muted-foreground text-sm font-medium leading-[18.20px] break-words">
            Everything you need to know about Watsonx Resilience Co-Pilot and how it protects your applications
          </p>
        </div>
      </div>
      <div className="w-full max-w-[600px] pt-0.5 pb-10 flex flex-col justify-start items-start gap-4 relative z-10">
        {faqData.map((faq, index) => (
          <FAQItem key={index} {...faq} isOpen={openItems.has(index)} onToggle={() => toggleItem(index)} />
        ))}
      </div>
    </section>
  )
}
