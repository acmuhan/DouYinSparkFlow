ALTER TABLE `plans` ADD `plugin_permissions` json;--> statement-breakpoint
ALTER TABLE `tasks` ADD `plugin_id` varchar(80) DEFAULT 'douyin_streak' NOT NULL;