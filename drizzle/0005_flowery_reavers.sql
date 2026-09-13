ALTER TABLE `accounts` ADD `inspection_status` varchar(16);--> statement-breakpoint
ALTER TABLE `accounts` ADD `inspection_message` varchar(255);--> statement-breakpoint
ALTER TABLE `accounts` ADD `checked_at` datetime(3);--> statement-breakpoint
ALTER TABLE `accounts` ADD `friends` json;