from agents.base import AgentBase
from services.llm_service import get_llm_response

class ChatAgent(AgentBase):
    """聊天智能体"""
    
    def __init__(self, config=None):
        super().__init__(config)
        self.type = "chat"
    
    def process(self, task):
        """处理任务"""
        prompt = f"请处理以下任务: {task.get('description', task.get('name', ''))}"
        response = get_llm_response(prompt)
        return {
            "task_id": task.get("id"),
            "result": response,
            "status": "completed"
        }
    
    def communicate(self, message):
        """与其他智能体通信"""
        prompt = f"请回复以下消息: {message.get('content')}"
        response = get_llm_response(prompt)
        return {
            "response": response
        }
