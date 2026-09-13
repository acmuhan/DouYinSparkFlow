CREATE TABLE `run_events` (
	`id` varchar(36) NOT NULL,
	`run_id` varchar(36) NOT NULL,
	`code` varchar(40) NOT NULL,
	`message` varchar(255) NOT NULL,
	`sent_count` int NOT NULL DEFAULT 0,
	`created_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
	CONSTRAINT `run_events_id` PRIMARY KEY(`id`)
);
--> statement-breakpoint
ALTER TABLE `run_events` ADD CONSTRAINT `run_events_run_id_runs_id_fk` FOREIGN KEY (`run_id`) REFERENCES `runs`(`id`) ON DELETE no action ON UPDATE no action;--> statement-breakpoint
CREATE INDEX `run_events_run_created` ON `run_events` (`run_id`,`created_at`);