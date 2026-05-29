import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: '智能知识库 - 知识问答系统',
  description: '企业内部知识库问答系统 + 语音对话助手',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen bg-gray-50">
        {children}
      </body>
    </html>
  );
}
