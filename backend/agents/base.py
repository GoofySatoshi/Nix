class AgentBase:
    """智能体基类"""
    
    def __init__(self, config=None):
        self.config = config or {}
        self.name = self.config.get("name", "Agent")
        self.type = self.config.get("type", "base")
    
    def process(self, task):
        """处理任务"""
        raise NotImplementedError("Subclasses must implement process method")
    
    def communicate(self, message):
        """与其他智能体通信"""
        raise NotImplementedError("Subclasses must implement communicate method")
    
    def get_status(self):
        """获取智能体状态"""
        return {
            "name": self.name,
            "type": self.type,
            "status": "active"
        }
