---
name: "task-splitter"
description: "Splits complex projects into manageable tasks with clear dependencies and priorities. Invoke when user needs to break down a project into actionable steps or when planning a new development project."
---

# Task Splitter

This skill helps break down complex projects into smaller, manageable tasks with clear dependencies and priorities.

## When to Use

Invoke this skill when:
- User needs to break down a complex project into actionable steps
- User is planning a new development project
- User wants to organize tasks for a multi-step process
- User needs to create a project roadmap with clear milestones

## How to Use

1. **Define the project scope**: Clearly describe the overall project goal and requirements
2. **Identify main components**: Break the project into major components or phases
3. **Split into tasks**: For each component, create specific, actionable tasks
4. **Establish dependencies**: Identify which tasks depend on others
5. **Set priorities**: Assign priority levels to tasks
6. **Estimate effort**: Provide rough time estimates for each task

## Example

### Project: Multi-Agent Collaboration System

**Main Components:**
1. Backend Development
2. Frontend Development
3. Database Design
4. API Integration
5. Testing and Deployment

**Tasks:**

**Backend Development** (Priority: High)
- Task 1: Set up FastAPI project structure (Estimate: 1 hour)
- Task 2: Implement database models (Estimate: 2 hours)
- Task 3: Create API endpoints for agents (Estimate: 3 hours)
- Task 4: Implement task management system (Estimate: 2 hours)
- Task 5: Add WebSocket support for real-time communication (Estimate: 2 hours)

**Frontend Development** (Priority: High)
- Task 6: Set up React + TypeScript project (Estimate: 1 hour)
- Task 7: Create agent dashboard component (Estimate: 2 hours)
- Task 8: Implement task manager interface (Estimate: 2 hours)
- Task 9: Build communication panel (Estimate: 2 hours)
- Task 10: Add responsive design (Estimate: 1 hour)

**Database Design** (Priority: Medium)
- Task 11: Design database schema (Estimate: 1 hour)
- Task 12: Set up SQLite database (Estimate: 30 minutes)

**API Integration** (Priority: Medium)
- Task 13: Test API endpoints (Estimate: 1 hour)
- Task 14: Implement error handling (Estimate: 1 hour)

**Testing and Deployment** (Priority: Low)
- Task 15: Write unit tests (Estimate: 2 hours)
- Task 16: Set up Docker containers (Estimate: 1 hour)
- Task 17: Deploy to production (Estimate: 1 hour)

## Output Format

When using this skill, provide the task breakdown in a structured format with:
- Project name
- Main components
- Tasks with descriptions, priorities, and estimates
- Dependencies between tasks

## Benefits

- Makes complex projects more manageable
- Provides clear roadmap for development
- Helps identify potential bottlenecks early
- Facilitates better resource allocation
- Improves project tracking and progress monitoring