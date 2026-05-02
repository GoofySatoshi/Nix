from agents.base import AgentBase
from agents.default_agent import DefaultAgent
from agents.chat_agent import ChatAgent

class AgentFactory:
    """智能体工厂"""
    
    @staticmethod
    def create_agent(agent_type, config=None):
        """根据类型创建智能体"""
        if agent_type == "default":
            return DefaultAgent(config)
        elif agent_type == "chat":
            return ChatAgent(config)
        else:
            # 默认创建默认智能体
            return DefaultAgent(config)
