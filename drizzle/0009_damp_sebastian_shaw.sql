ALTER TABLE `tasks` MODIFY COLUMN `account_id` varchar(36);--> statement-breakpoint
ALTER TABLE `tasks` ADD `plugin_config` json;