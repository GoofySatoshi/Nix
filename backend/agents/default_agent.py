from agents.base import AgentBase

class DefaultAgent(AgentBase):
    """默认智能体"""
    
    def __init__(self, config=None):
        super().__init__(config)
        self.type = "default"
    
    def process(self, task):
        """处理任务"""
        return {
            "task_id": task.get("id"),
            "result": f"Default agent processed task: {task.get('name')}",
            "status": "completed"
        }
    
    def communicate(self, message):
        """与其他智能体通信"""
        return {
            "response": f"Default agent received: {message.get('content')}"
        }
