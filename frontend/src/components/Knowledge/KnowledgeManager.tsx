'use client';

import { useState, useEffect } from 'react';

interface KnowledgeStats {
  name: string;
  document_count: number;
}

export default function KnowledgeManager() {
  const [stats, setStats] = useState<KnowledgeStats | null>(null);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<any[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [uploadMsg, setUploadMsg] = useState('');

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      const res = await fetch('/api/v1/knowledge/stats');
      if (res.ok) setStats(await res.json());
    } catch {}
  };

  const handleSearch = async () => {
    if (!query.trim()) return;
    setIsSearching(true);
    try {
      const res = await fetch(
        `/api/v1/knowledge/search?query=${encodeURIComponent(query)}&top_k=5`
      );
      if (res.ok) {
        const data = await res.json();
        setResults(data.results || []);
      }
    } catch {} finally {
      setIsSearching(false);
    }
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    setUploadMsg('上传中...');
    try {
      const res = await fetch('/api/v1/knowledge/upload', {
        method: 'POST',
        body: formData,
      });
      if (res.ok) {
        const data = await res.json();
        setUploadMsg(`上传成功: ${data.chunks_created} 个分段`);
        loadStats();
      } else {
        setUploadMsg('上传失败');
      }
    } catch {
      setUploadMsg('上传出错');
    }
  };

  return (
    <div className="p-4 space-y-6">
      {/* 统计卡片 */}
      <div className="bg-white border rounded-xl p-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-2">知识库统计</h3>
        <div className="flex gap-4">
          <div className="flex-1 bg-blue-50 rounded-lg p-3">
            <p className="text-2xl font-bold text-blue-600">
              {stats?.document_count ?? '-'}
            </p>
            <p className="text-xs text-gray-500">总文档片段</p>
          </div>
          <div className="flex-1 bg-green-50 rounded-lg p-3">
            <p className="text-2xl font-bold text-green-600">
              {stats?.name ?? '-'}
            </p>
            <p className="text-xs text-gray-500">集合名称</p>
          </div>
        </div>
      </div>

      {/* 搜索 */}
      <div className="bg-white border rounded-xl p-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">知识检索</h3>
        <div className="flex gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="输入检索关键词..."
            className="flex-1 border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
          <button
            onClick={handleSearch}
            disabled={isSearching}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm"
          >
            {isSearching ? '搜索中...' : '搜索'}
          </button>
        </div>
        {results.length > 0 && (
          <div className="mt-3 space-y-2">
            {results.map((r, i) => (
              <div key={i} className="bg-gray-50 rounded-lg p-3">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded">
                    {(r.score * 100).toFixed(0)}%
                  </span>
                  <span className="text-xs text-gray-400">
                    {r.metadata?.source_file || '未知来源'}
                  </span>
                </div>
                <p className="text-sm text-gray-700">{r.text.slice(0, 300)}...</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 上传 */}
      <div className="bg-white border rounded-xl p-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">文档上传</h3>
        <input
          type="file"
          onChange={handleUpload}
          accept=".txt,.md,.pdf,.docx,.html"
          className="text-sm"
        />
        {uploadMsg && (
          <p className={`text-xs mt-2 ${
            uploadMsg.includes('成功') ? 'text-green-600' : 'text-red-500'
          }`}>
            {uploadMsg}
          </p>
        )}
      </div>
    </div>
  );
}
