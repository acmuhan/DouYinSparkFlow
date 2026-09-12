CREATE INDEX `runs_task_status` ON `runs` (`task_id`,`status`);--> statement-breakpoint
CREATE INDEX `runs_status_lease` ON `runs` (`status`,`lease_until`);--> statement-breakpoint
CREATE INDEX `tasks_schedule_due` ON `tasks` (`enabled`,`archived`,`next_run_at`);