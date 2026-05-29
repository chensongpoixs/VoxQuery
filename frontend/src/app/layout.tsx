import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: '能源智库 - 知识问答系统',
  description: '面向能源行业的内部业务知识库问答系统 + 语音对话助手',
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
