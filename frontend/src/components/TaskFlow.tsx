import React, { useCallback, useState, useMemo } from 'react';
import ReactFlow, { Node, Edge, useNodesState, useEdgesState, addEdge, Background, Controls, Connection, NodeProps } from 'reactflow';
import 'reactflow/dist/style.css';

interface Task {
  id: number;
  name: string;
  description?: string;
  status: string;
  agent_id?: number;
  dependencies: number[];
}

interface TaskFlowProps {
  tasks: Task[];
}

const statusLabels: Record<string, string> = {
  pending: '待处理', running: '运行中', completed: '已完成', failed: '失败'
};

const TaskFlow: React.FC<TaskFlowProps> = ({ tasks }) => {
  const [selectedNode, setSelectedNode] = useState<Task | null>(null);

  // 生成节点
  const initialNodes: Node[] = useMemo(() => {
    return tasks.map((task, index) => {
      let bgColor: string;
      let borderColor: string;
      let textColor: string;

      switch (task.status) {
        case 'completed':
          bgColor = 'rgba(16,185,129,0.15)'; borderColor = 'rgba(16,185,129,0.5)'; textColor = '#10b981';
          break;
        case 'running':
          bgColor = 'rgba(245,158,11,0.15)'; borderColor = 'rgba(245,158,11,0.5)'; textColor = '#f59e0b';
          break;
        case 'failed':
          bgColor = 'rgba(239,68,68,0.15)'; borderColor = 'rgba(239,68,68,0.5)'; textColor = '#ef4444';
          break;
        case 'pending':
        default:
          bgColor = 'rgba(139,92,246,0.15)'; borderColor = 'rgba(139,92,246,0.5)'; textColor = '#a78bfa';
          break;
      }

      return {
        id: task.id.toString(),
        type: 'default',
        data: {
          label: `${task.name} (ID: ${task.id})`,
        },
        position: {
          x: 100 + (index % 3) * 320,
          y: 100 + Math.floor(index / 3) * 220,
        },
        style: {
          backgroundColor: bgColor,
          border: `2px solid ${borderColor}`,
          color: textColor,
          borderRadius: '16px',
          padding: '12px 16px',
          fontSize: '13px',
          fontWeight: 600,
          minWidth: '160px',
        },
      };
    });
  }, [tasks]);

  // 生成边
  const initialEdges: Edge[] = useMemo(() => {
    const edges: Edge[] = [];
    tasks.forEach((task) => {
      task.dependencies.forEach((depId) => {
        edges.push({
          id: `edge-${depId}-${task.id}`,
          source: depId.toString(),
          target: task.id.toString(),
          animated: true,
          style: { stroke: 'rgba(139,92,246,0.4)', strokeWidth: 2 },
        });
      });
    });
    return edges;
  }, [tasks]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  const onConnect = useCallback((params: Connection) => {
    setEdges((eds) => addEdge(params, eds));
  }, [setEdges]);

  // 节点点击处理
  const onNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    const task = tasks.find(t => t.id.toString() === node.id);
    if (task) {
      setSelectedNode(prev => prev?.id === task.id ? null : task);
    }
  }, [tasks]);

  return (
    <div style={{
      width: '100%', height: 600, border: '1px solid var(--border-color)',
      borderRadius: 'var(--radius-card)', overflow: 'hidden',
      backdropFilter: 'blur(10px)', background: 'var(--glass-bg-subtle)', position: 'relative'
    }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={onNodeClick}
        fitView
        style={{ backgroundColor: 'transparent' }}
      >
        <Background color="rgba(139,92,246,0.08)" gap={20} />
        <Controls />
      </ReactFlow>

      {/* 节点详情 Tooltip */}
      {selectedNode && (
        <div style={{
          position: 'absolute', top: '12px', right: '12px', zIndex: 10,
          background: 'var(--bg-surface)', border: '1px solid var(--border-color)',
          borderRadius: '12px', padding: '16px', maxWidth: '280px',
          boxShadow: '0 8px 30px rgba(0,0,0,0.15)', backdropFilter: 'blur(20px)'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <strong style={{ color: 'var(--text-primary)' }}>{selectedNode.name}</strong>
            <button
              onClick={() => setSelectedNode(null)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', fontSize: '18px', lineHeight: 1 }}
            >x</button>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginBottom: '8px' }}>
            {selectedNode.description || '无描述'}
          </p>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '4px' }}>
            状态: <span style={{ fontWeight: 600 }}>{statusLabels[selectedNode.status]}</span>
          </p>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '4px' }}>
            智能体ID: {selectedNode.agent_id || '未分配'}
          </p>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
            依赖: {selectedNode.dependencies?.length ? selectedNode.dependencies.join(', ') : '无'}
          </p>
        </div>
      )}
    </div>
  );
};

export default TaskFlow;
