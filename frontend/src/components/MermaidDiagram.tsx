import React, { useEffect, useRef, useState } from 'react';
import mermaid from 'mermaid';

// 初始化 Mermaid 配置
mermaid.initialize({
  startOnLoad: false,
  theme: 'default',
  securityLevel: 'loose',
  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
});

interface MermaidDiagramProps {
  code: string;
}

const MermaidDiagram: React.FC<MermaidDiagramProps> = ({ code }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [svg, setSvg] = useState<string>('');
  const [error, setError] = useState<string>('');

  useEffect(() => {
    if (!code || !code.trim()) {
      setSvg('');
      setError('');
      return;
    }

    const renderDiagram = async () => {
      try {
        const id = `mermaid-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
        const { svg: renderedSvg } = await mermaid.render(id, code.trim());
        setSvg(renderedSvg);
        setError('');
      } catch (err: any) {
        setSvg('');
        setError(err.message || 'Mermaid 语法错误');
      }
    };

    renderDiagram();
  }, [code]);

  if (!code) {
    return (
      <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '40px' }}>
        暂无 Mermaid 工作流语法
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: '16px' }}>
        <div style={{
          background: 'var(--bg-surface-subtle)',
          border: '1px solid var(--border-color)',
          borderRadius: '12px',
          padding: '16px',
          marginBottom: '12px'
        }}>
          <pre style={{ fontFamily: 'Monaco, monospace', color: 'var(--text-primary)', lineHeight: 1.6, fontSize: '14px', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
            {code}
          </pre>
        </div>
        <div style={{
          background: 'rgba(239,68,68,0.1)',
          border: '1px solid rgba(239,68,68,0.3)',
          borderRadius: '8px',
          padding: '12px 16px',
          color: '#ef4444',
          fontSize: '14px'
        }}>
          <strong>渲染错误:</strong> {error}
        </div>
      </div>
    );
  }

  return (
    <div ref={containerRef} style={{ width: '100%', height: '100%', overflow: 'auto' }}>
      <div
        dangerouslySetInnerHTML={{ __html: svg }}
        style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '200px',
          padding: '16px'
        }}
      />
    </div>
  );
};

export default MermaidDiagram;
