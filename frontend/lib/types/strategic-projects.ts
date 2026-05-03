export type ProjectStatus = "on-track" | "in-progress" | "at-risk" | "planning";
export type MilestoneStatus = "done" | "current" | "pending";

export interface Milestone {
  id: string;
  text: string;
  status: MilestoneStatus;
  dueDate?: string;
}

export interface StrategicProject {
  id: string;
  name: string;
  description: string;
  status: ProjectStatus;
  progressPercent: number;
  deadline: string;
  owner: string;
  milestones: Milestone[];
}
