from sqlalchemy.orm import Session
from models import Agent
from schemas.agent import AgentCreate, AgentUpdate
from agents.factory import AgentFactory

# 智能体实例缓存
agent_instances = {}

def create_agent(db: Session, agent: AgentCreate) -> Agent:
    """创建智能体"""
    db_agent = Agent(
        name=agent.name,
        type=agent.type,
        personality=agent.personality,
        config=agent.config,
        config_id=agent.config_id,
        avatar=agent.avatar,
        status="stopped"
    )
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)
    return db_agent

def get_agent(db: Session, agent_id: int) -> Agent:
    """获取智能体"""
    return db.query(Agent).filter(Agent.id == agent_id).first()

def get_agents(db: Session) -> list[Agent]:
    """获取所有智能体"""
    return db.query(Agent).all()

def update_agent(db: Session, agent_id: int, agent: AgentUpdate) -> Agent:
    """更新智能体"""
    db_agent = get_agent(db, agent_id)
    if not db_agent:
        return None
    
    if agent.name is not None:
        db_agent.name = agent.name
    if agent.type is not None:
        db_agent.type = agent.type
    if agent.personality is not None:
        db_agent.personality = agent.personality
    if agent.config is not None:
        db_agent.config = agent.config
    if agent.config_id is not None:
        db_agent.config_id = agent.config_id
    if agent.avatar is not None:
        db_agent.avatar = agent.avatar

    db.commit()
    db.refresh(db_agent)
    return db_agent

def delete_agent(db: Session, agent_id: int) -> bool:
    """删除智能体"""
    db_agent = get_agent(db, agent_id)
    if not db_agent:
        return False
    
    # 停止智能体
    if db_agent.status == "running":
        stop_agent(db, agent_id)
    
    # 从缓存中移除
    if agent_id in agent_instances:
        del agent_instances[agent_id]
    
    db.delete(db_agent)
    db.commit()
    return True

def start_agent(db: Session, agent_id: int) -> Agent:
    """启动智能体"""
    db_agent = get_agent(db, agent_id)
    if not db_agent:
        return None
    
    # 检查智能体是否已在运行
    if db_agent.status == "running":
        return db_agent
    
    # 使用 AgentFactory 创建真实的智能体实例
    config = {
        "name": db_agent.name,
        "type": db_agent.type,
        "personality": db_agent.personality,
        **(db_agent.config or {})
    }
    agent_instance = AgentFactory.create_agent(db_agent.type, config)
    agent_instances[agent_id] = agent_instance
    
    # 更新状态
    db_agent.status = "running"
    db.commit()
    db.refresh(db_agent)
    return db_agent

def stop_agent(db: Session, agent_id: int) -> Agent:
    """停止智能体"""
    db_agent = get_agent(db, agent_id)
    if not db_agent:
        return None
    
    # 检查智能体是否已停止
    if db_agent.status == "stopped":
        return db_agent
    
    # 移除智能体实例
    if agent_id in agent_instances:
        del agent_instances[agent_id]
    
    # 更新状态
    db_agent.status = "stopped"
    db.commit()
    db.refresh(db_agent)
    return db_agent

def get_agent_instance(agent_id: int):
    """获取智能体实例"""
    return agent_instances.get(agent_id)

def get_agent_types(db: Session) -> list[str]:
    """获取所有唯一的智能体类型"""
    # 从数据库中获取所有唯一的智能体类型
    types = db.query(Agent.type).distinct().all()
    # 提取类型值并返回列表
    return [t[0] for t in types]
