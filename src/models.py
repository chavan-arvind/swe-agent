from pydantic import BaseModel, Field
from typing import List

class Subtask(BaseModel):
    description: str = Field(..., description="Description of the subtask")
    estimated_time: str = Field(..., description="Estimated time to complete the subtask")

class ResolutionPlan(BaseModel):
    issue_analysis: str = Field(..., description="Brief analysis of the issue and its implications")
    subtasks: List[Subtask] = Field(..., description="List of subtasks to resolve the issue")
    dependencies: List[str] = Field(..., description="List of dependencies between subtasks or external factors")
    potential_challenges: List[str] = Field(..., description="List of potential roadblocks or challenges")
    testing_strategy: str = Field(..., description="Suggested basic testing strategy for the resolution")
    documentation_updates: List[str] = Field(..., description="Recommended documentation updates")

# Add other models here if needed
