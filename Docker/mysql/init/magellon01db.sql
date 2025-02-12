/*
SQLyog Ultimate v13.1.1 (64 bit)
MySQL - 10.5.23-MariaDB-0+deb11u1 : Database - magellon05
*********************************************************************
*/

/*!40101 SET NAMES utf8 */;

/*!40101 SET SQL_MODE=''*/;

/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;
CREATE DATABASE /*!32312 IF NOT EXISTS*/`magellon01` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci */;

USE `magellon01`;

/*Table structure for table `atlas` */

DROP TABLE IF EXISTS `atlas`;

CREATE TABLE `atlas` (
  `oid` BINARY(16) NOT NULL,
  `name` VARCHAR(100) DEFAULT NULL,
  `meta` LONGTEXT DEFAULT NULL,
  `OptimisticLockField` INT(11) DEFAULT NULL,
  `GCRecord` INT(11) DEFAULT NULL,
  `session_id` BINARY(16) DEFAULT NULL,
  PRIMARY KEY (`oid`),
  KEY `iGCRecord_Atlas` (`GCRecord`),
  KEY `imsession_id_Atlas` (`session_id`),
  CONSTRAINT `FK_Atlas_msession_id` FOREIGN KEY (`session_id`) REFERENCES `msession` (`oid`)
) ENGINE=INNODB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci AVG_ROW_LENGTH=12288;

/*Data for the table `atlas` */

/*Table structure for table `camera` */

DROP TABLE IF EXISTS `camera`;

CREATE TABLE `camera` (
  `oid` BINARY(16) NOT NULL,
  `name` VARCHAR(30) DEFAULT NULL,
  `OptimisticLockField` INT(11) DEFAULT NULL,
  `GCRecord` INT(11) DEFAULT NULL,
  PRIMARY KEY (`oid`),
  KEY `iGCRecord_Camera` (`GCRecord`)
) ENGINE=INNODB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci AVG_ROW_LENGTH=5461;

/*Data for the table `camera` */

INSERT  INTO `camera`(`oid`,`name`,`OptimisticLockField`,`GCRecord`) VALUES 
('?�_dWEb��,�?f��','Kasha Lab #1 Cam',NULL,NULL),
('x�����OǢ|�6_��','Alpine',NULL,NULL);

/*Table structure for table `image` */

DROP TABLE IF EXISTS `image`;

CREATE TABLE `image` (
  `oid` BINARY(16) NOT NULL,
  `name` VARCHAR(100) DEFAULT NULL,
  `frame_name` VARCHAR(100) DEFAULT NULL,
  `path` VARCHAR(300) DEFAULT NULL,
  `parent_id` BINARY(16) DEFAULT NULL,
  `session_id` BINARY(16) DEFAULT NULL,
  `magnification` bigint(20) DEFAULT NULL,
  `dose` decimal(28,8) DEFAULT NULL,
  `focus` decimal(28,8) DEFAULT NULL,
  `defocus` decimal(28,8) DEFAULT NULL,
  `spot_size` bigint(20) DEFAULT NULL,
  `intensity` decimal(28,8) DEFAULT NULL,
  `shift_x` decimal(28,8) DEFAULT NULL,
  `shift_y` decimal(28,8) DEFAULT NULL,
  `beam_shift_x` decimal(28,8) DEFAULT NULL,
  `beam_shift_y` decimal(28,8) DEFAULT NULL,
  `reset_focus` bigint(20) DEFAULT NULL,
  `screen_current` bigint(20) DEFAULT NULL,
  `beam_bank` varchar(150) DEFAULT NULL,
  `condenser_x` decimal(28,8) DEFAULT NULL,
  `condenser_y` decimal(28,8) DEFAULT NULL,
  `objective_x` decimal(28,8) DEFAULT NULL,
  `objective_y` decimal(28,8) DEFAULT NULL,
  `dimension_x` bigint(20) DEFAULT NULL,
  `dimension_y` bigint(20) DEFAULT NULL,
  `binning_x` bigint(20) DEFAULT NULL,
  `binning_y` bigint(20) DEFAULT NULL,
  `offset_x` bigint(20) DEFAULT NULL,
  `offset_y` bigint(20) DEFAULT NULL,
  `exposure_time` decimal(28,8) DEFAULT NULL,
  `exposure_type` bigint(20) DEFAULT NULL,
  `pixel_size_x` decimal(28,8) DEFAULT NULL,
  `pixel_size_y` decimal(28,8) DEFAULT NULL,
  `energy_filtered` bit(1) DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  `previous_id` bigint(20) DEFAULT NULL,
  `pixel_size` double DEFAULT NULL,
  `level` int(11) DEFAULT NULL,
  `atlas_delta_row` double DEFAULT NULL,
  `atlas_delta_column` double DEFAULT NULL,
  `atlas_dimxy` double DEFAULT NULL,
  `metadata` longtext DEFAULT NULL,
  `stage_alpha_tilt` double DEFAULT NULL,
  `stage_x` double DEFAULT NULL,
  `stage_y` double DEFAULT NULL,
  `atlas_id` binary(16) DEFAULT NULL,
  `last_accessed_date` datetime DEFAULT NULL,
  `frame_count` int(11) DEFAULT NULL,
  `acceleration_voltage` double DEFAULT NULL,
  `spherical_aberration` double DEFAULT NULL,
  PRIMARY KEY (`oid`),
  KEY `iGCRecord_Image` (`GCRecord`),
  KEY `iparent_Image` (`parent_id`),
  KEY `isession_Image` (`session_id`),
  KEY `iatlas_Image` (`atlas_id`),
  CONSTRAINT `FK_Image_atlas` FOREIGN KEY (`atlas_id`) REFERENCES `atlas` (`oid`),
  CONSTRAINT `FK_Image_parent` FOREIGN KEY (`parent_id`) REFERENCES `image` (`oid`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `FK_Image_session` FOREIGN KEY (`session_id`) REFERENCES `msession` (`oid`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci AVG_ROW_LENGTH=286;

/*Data for the table `image` */

/*Table structure for table `image_job` */

DROP TABLE IF EXISTS `image_job`;

CREATE TABLE `image_job` (
  `oid` binary(16) NOT NULL,
  `name` varchar(100) DEFAULT NULL,
  `description` text DEFAULT NULL,
  `created_date` datetime DEFAULT NULL,
  `start_date` datetime DEFAULT NULL,
  `end_date` datetime DEFAULT NULL,
  `user_id` varchar(100) DEFAULT NULL,
  `project_id` varchar(100) DEFAULT NULL,
  `msession_id` varchar(100) DEFAULT NULL,
  `status_id` smallint(5) unsigned DEFAULT NULL,
  `type_id` smallint(5) unsigned DEFAULT NULL,
  `data` longtext DEFAULT NULL,
  `data_json` longtext DEFAULT NULL,
  `processed_json` longtext DEFAULT NULL,
  `output_directory` varchar(250) DEFAULT NULL,
  `direction` smallint(5) unsigned DEFAULT NULL,
  `image_selection_criteria` text DEFAULT NULL,
  `pipeline_id` binary(16) DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  PRIMARY KEY (`oid`),
  KEY `iGCRecord_image_job` (`GCRecord`),
  KEY `ipipeline_id_image_job` (`pipeline_id`),
  CONSTRAINT `FK_image_job_pipeline_id` FOREIGN KEY (`pipeline_id`) REFERENCES `pipeline` (`oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/*Data for the table `image_job` */

/*Table structure for table `image_job_task` */

DROP TABLE IF EXISTS `image_job_task`;

CREATE TABLE `image_job_task` (
  `oid` binary(16) NOT NULL,
  `job_id` binary(16) DEFAULT NULL,
  `image_id` binary(16) DEFAULT NULL,
  `status_id` smallint(5) unsigned DEFAULT NULL,
  `type_id` smallint(5) unsigned DEFAULT NULL,
  `data` longtext DEFAULT NULL,
  `data_json` longtext DEFAULT NULL,
  `processed_json` longtext DEFAULT NULL,
  `pipeline_item_id` binary(16) DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  `stage` int(11) DEFAULT NULL,
  `image_name` varchar(255) DEFAULT NULL,
  `image_path` varchar(255) DEFAULT NULL,
  `frame_name` varchar(255) DEFAULT NULL,
  `frame_path` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`oid`),
  KEY `iGCRecord_image_job_task` (`GCRecord`),
  KEY `ijob_id_image_job_task` (`job_id`),
  KEY `iimage_id_image_job_task` (`image_id`),
  KEY `ipipeline_item_id_image_job_task` (`pipeline_item_id`),
  CONSTRAINT `FK_image_job_task_image_id` FOREIGN KEY (`image_id`) REFERENCES `image` (`oid`),
  CONSTRAINT `FK_image_job_task_job_id` FOREIGN KEY (`job_id`) REFERENCES `image_job` (`oid`),
  CONSTRAINT `FK_image_job_task_pipeline_item_id` FOREIGN KEY (`pipeline_item_id`) REFERENCES `pipeline_item` (`oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/*Data for the table `image_job_task` */

/*Table structure for table `image_meta_data` */

DROP TABLE IF EXISTS `image_meta_data`;

CREATE TABLE `image_meta_data` (
  `oid` binary(16) NOT NULL,
  `omid` bigint(20) DEFAULT NULL,
  `ouid` varchar(20) DEFAULT NULL,
  `created_date` datetime DEFAULT NULL,
  `created_by` binary(16) DEFAULT NULL,
  `last_modified_date` datetime DEFAULT NULL,
  `last_modified_by` binary(16) DEFAULT NULL,
  `deleted_date` datetime DEFAULT NULL,
  `deleted_by` binary(16) DEFAULT NULL,
  `sync_status` int(11) DEFAULT NULL,
  `version` varchar(10) DEFAULT NULL,
  `image_id` binary(16) DEFAULT NULL,
  `name` varchar(100) DEFAULT NULL,
  `alias` varchar(100) DEFAULT NULL,
  `job_id` binary(16) DEFAULT NULL,
  `task_id` binary(16) DEFAULT NULL,
  `category_id` int(11) DEFAULT NULL,
  `data` longtext DEFAULT NULL,
  `data_json` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`data_json`)),
  `processed_json` longtext DEFAULT NULL,
  `plugin_id` binary(16) DEFAULT NULL,
  `status_id` int(11) DEFAULT NULL,
  `plugin_type_id` binary(16) DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  `type` int(11) DEFAULT NULL,
  PRIMARY KEY (`oid`),
  KEY `iGCRecord_image_meta_data` (`GCRecord`),
  KEY `icreated_by_image_meta_data` (`created_by`),
  KEY `ilast_modified_by_image_meta_data` (`last_modified_by`),
  KEY `ideleted_by_image_meta_data` (`deleted_by`),
  KEY `iimage_id_image_meta_data` (`image_id`),
  KEY `ijob_id_image_meta_data` (`job_id`),
  KEY `itask_id_image_meta_data` (`task_id`),
  KEY `icategory_id_image_meta_data` (`category_id`),
  KEY `iplugin_id_image_meta_data` (`plugin_id`),
  KEY `iplugin_type_id_image_meta_data` (`plugin_type_id`),
  CONSTRAINT `FK_image_meta_data_category_id` FOREIGN KEY (`category_id`) REFERENCES `image_meta_data_category` (`oid`),
  CONSTRAINT `FK_image_meta_data_created_by` FOREIGN KEY (`created_by`) REFERENCES `sys_sec_user` (`oid`),
  CONSTRAINT `FK_image_meta_data_deleted_by` FOREIGN KEY (`deleted_by`) REFERENCES `sys_sec_user` (`oid`),
  CONSTRAINT `FK_image_meta_data_image_id` FOREIGN KEY (`image_id`) REFERENCES `image` (`oid`),
  CONSTRAINT `FK_image_meta_data_job_id` FOREIGN KEY (`job_id`) REFERENCES `image_job` (`oid`),
  CONSTRAINT `FK_image_meta_data_last_modified_by` FOREIGN KEY (`last_modified_by`) REFERENCES `sys_sec_user` (`oid`),
  CONSTRAINT `FK_image_meta_data_plugin_id` FOREIGN KEY (`plugin_id`) REFERENCES `plugin` (`oid`),
  CONSTRAINT `FK_image_meta_data_plugin_type_id` FOREIGN KEY (`plugin_type_id`) REFERENCES `plugin_type` (`oid`),
  CONSTRAINT `FK_image_meta_data_task_id` FOREIGN KEY (`task_id`) REFERENCES `image_job_task` (`oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/*Data for the table `image_meta_data` */

/*Table structure for table `image_meta_data_category` */

DROP TABLE IF EXISTS `image_meta_data_category`;

CREATE TABLE `image_meta_data_category` (
  `oid` int(11) NOT NULL,
  `name` varchar(100) DEFAULT NULL,
  `parent_id` int(11) DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  PRIMARY KEY (`oid`),
  KEY `iGCRecord_image_meta_data_category` (`GCRecord`),
  KEY `iparent_id_image_meta_data_category` (`parent_id`),
  CONSTRAINT `FK_image_meta_data_category_parent_id` FOREIGN KEY (`parent_id`) REFERENCES `image_meta_data_category` (`oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/*Data for the table `image_meta_data_category` */

insert  into `image_meta_data_category`(`oid`,`name`,`parent_id`,`OptimisticLockField`,`GCRecord`) values 
(4,'Particle Picking',NULL,NULL,NULL),
(10,'Other',NULL,NULL,NULL),
(3,'Frame Alignment',NULL,NULL,NULL),
(2,'CTF',NULL,NULL,NULL),
(1,'FFT',NULL,NULL,NULL);

/*Table structure for table `microscope` */

DROP TABLE IF EXISTS `microscope`;

CREATE TABLE `microscope` (
  `oid` binary(16) NOT NULL,
  `name` varchar(30) DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  PRIMARY KEY (`oid`),
  KEY `iGCRecord_Microscope` (`GCRecord`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

/*Data for the table `microscope` */

/*Table structure for table `msession` */

DROP TABLE IF EXISTS `msession`;

CREATE TABLE `msession` (
  `oid` binary(16) NOT NULL,
  `name` varchar(50) DEFAULT NULL,
  `project_id` binary(16) DEFAULT NULL,
  `site_id` binary(16) DEFAULT NULL,
  `user_id` binary(16) DEFAULT NULL,
  `description` varchar(250) DEFAULT NULL,
  `start_on` datetime DEFAULT NULL,
  `end_on` datetime DEFAULT NULL,
  `microscope_id` binary(16) DEFAULT NULL,
  `camera_id` binary(16) DEFAULT NULL,
  `sample_type` binary(16) DEFAULT NULL,
  `sample_name` varchar(50) DEFAULT NULL,
  `sample_grid_type` binary(16) DEFAULT NULL,
  `sample_sequence` text DEFAULT NULL,
  `sample_procedure` longtext DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  `last_accessed_date` datetime DEFAULT NULL,
  PRIMARY KEY (`oid`),
  KEY `iGCRecord_MSession` (`GCRecord`),
  KEY `iproject_MSession` (`project_id`),
  KEY `isite_MSession` (`site_id`),
  KEY `iuser_MSession` (`user_id`),
  KEY `imicroscope_MSession` (`microscope_id`),
  KEY `icamera_MSession` (`camera_id`),
  KEY `isample_type_MSession` (`sample_type`),
  KEY `isample_grid_type_MSession` (`sample_grid_type`),
  CONSTRAINT `FK_MSession_camera` FOREIGN KEY (`camera_id`) REFERENCES `camera` (`oid`),
  CONSTRAINT `FK_MSession_microscope` FOREIGN KEY (`microscope_id`) REFERENCES `microscope` (`oid`),
  CONSTRAINT `FK_MSession_project` FOREIGN KEY (`project_id`) REFERENCES `project` (`oid`),
  CONSTRAINT `FK_MSession_sample_grid_type` FOREIGN KEY (`sample_grid_type`) REFERENCES `sample_grid_type` (`oid`),
  CONSTRAINT `FK_MSession_sample_type` FOREIGN KEY (`sample_type`) REFERENCES `sample_type` (`oid`),
  CONSTRAINT `FK_MSession_site` FOREIGN KEY (`site_id`) REFERENCES `site` (`oid`),
  CONSTRAINT `FK_MSession_user` FOREIGN KEY (`user_id`) REFERENCES `sys_sec_user` (`oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci AVG_ROW_LENGTH=16384;

/*Data for the table `msession` */

insert  into `msession`(`oid`,`name`,`project_id`,`site_id`,`user_id`,`description`,`start_on`,`end_on`,`microscope_id`,`camera_id`,`sample_type`,`sample_name`,`sample_grid_type`,`sample_sequence`,`sample_procedure`,`OptimisticLockField`,`GCRecord`,`last_accessed_date`) values 
('�L�\rF\\���	4��','23apr13a','勳l��B��yхъ�',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL),
('���գAM��ן�.	�','22apr01a','勳l��B��yхъ�',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL);

/*Table structure for table `pipeline` */

DROP TABLE IF EXISTS `pipeline`;

CREATE TABLE `pipeline` (
  `oid` binary(16) NOT NULL,
  `omid` bigint(20) DEFAULT NULL,
  `ouid` varchar(20) DEFAULT NULL,
  `created_date` datetime DEFAULT NULL,
  `created_by` binary(16) DEFAULT NULL,
  `last_modified_date` datetime DEFAULT NULL,
  `last_modified_by` binary(16) DEFAULT NULL,
  `deleted_date` datetime DEFAULT NULL,
  `deleted_by` binary(16) DEFAULT NULL,
  `sync_status` int(11) DEFAULT NULL,
  `version` varchar(10) DEFAULT NULL,
  `name` varchar(100) DEFAULT NULL,
  `data` longtext DEFAULT NULL,
  `data_json` longtext DEFAULT NULL,
  `Description` longtext DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  PRIMARY KEY (`oid`),
  KEY `iGCRecord_pipeline` (`GCRecord`),
  KEY `icreated_by_pipeline` (`created_by`),
  KEY `ilast_modified_by_pipeline` (`last_modified_by`),
  KEY `ideleted_by_pipeline` (`deleted_by`),
  CONSTRAINT `FK_pipeline_created_by` FOREIGN KEY (`created_by`) REFERENCES `sys_sec_user` (`oid`),
  CONSTRAINT `FK_pipeline_deleted_by` FOREIGN KEY (`deleted_by`) REFERENCES `sys_sec_user` (`oid`),
  CONSTRAINT `FK_pipeline_last_modified_by` FOREIGN KEY (`last_modified_by`) REFERENCES `sys_sec_user` (`oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/*Data for the table `pipeline` */

/*Table structure for table `pipeline_item` */

DROP TABLE IF EXISTS `pipeline_item`;

CREATE TABLE `pipeline_item` (
  `oid` binary(16) NOT NULL,
  `omid` bigint(20) DEFAULT NULL,
  `ouid` varchar(20) DEFAULT NULL,
  `created_date` datetime DEFAULT NULL,
  `created_by` binary(16) DEFAULT NULL,
  `last_modified_date` datetime DEFAULT NULL,
  `last_modified_by` binary(16) DEFAULT NULL,
  `deleted_date` datetime DEFAULT NULL,
  `deleted_by` binary(16) DEFAULT NULL,
  `sync_status` int(11) DEFAULT NULL,
  `version` varchar(10) DEFAULT NULL,
  `name` varchar(100) DEFAULT NULL,
  `pipeline_id` binary(16) DEFAULT NULL,
  `plugin_id` varchar(100) DEFAULT NULL,
  `status` varchar(100) DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  PRIMARY KEY (`oid`),
  KEY `iGCRecord_pipeline_item` (`GCRecord`),
  KEY `icreated_by_pipeline_item` (`created_by`),
  KEY `ilast_modified_by_pipeline_item` (`last_modified_by`),
  KEY `ideleted_by_pipeline_item` (`deleted_by`),
  KEY `ipipeline_id_pipeline_item` (`pipeline_id`),
  CONSTRAINT `FK_pipeline_item_created_by` FOREIGN KEY (`created_by`) REFERENCES `sys_sec_user` (`oid`),
  CONSTRAINT `FK_pipeline_item_deleted_by` FOREIGN KEY (`deleted_by`) REFERENCES `sys_sec_user` (`oid`),
  CONSTRAINT `FK_pipeline_item_last_modified_by` FOREIGN KEY (`last_modified_by`) REFERENCES `sys_sec_user` (`oid`),
  CONSTRAINT `FK_pipeline_item_pipeline_id` FOREIGN KEY (`pipeline_id`) REFERENCES `pipeline` (`oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/*Data for the table `pipeline_item` */

/*Table structure for table `plugin` */

DROP TABLE IF EXISTS `plugin`;

CREATE TABLE `plugin` (
  `oid` binary(16) NOT NULL,
  `omid` bigint(20) DEFAULT NULL,
  `ouid` varchar(20) DEFAULT NULL,
  `created_date` datetime DEFAULT NULL,
  `created_by` binary(16) DEFAULT NULL,
  `last_modified_date` datetime DEFAULT NULL,
  `last_modified_by` binary(16) DEFAULT NULL,
  `deleted_date` datetime DEFAULT NULL,
  `deleted_by` binary(16) DEFAULT NULL,
  `sync_status` int(11) DEFAULT NULL,
  `version` varchar(10) DEFAULT NULL,
  `name` varchar(100) DEFAULT NULL,
  `author` varchar(100) DEFAULT NULL,
  `copyright` text DEFAULT NULL,
  `type_id` binary(16) DEFAULT NULL,
  `status_id` int(11) DEFAULT NULL,
  `coresponding` varchar(100) DEFAULT NULL,
  `documentation` longtext DEFAULT NULL,
  `website` varchar(250) DEFAULT NULL,
  `input_json` longtext DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  PRIMARY KEY (`oid`),
  KEY `iGCRecord_plugin` (`GCRecord`),
  KEY `icreated_by_plugin` (`created_by`),
  KEY `ilast_modified_by_plugin` (`last_modified_by`),
  KEY `ideleted_by_plugin` (`deleted_by`),
  KEY `itype_id_plugin` (`type_id`),
  CONSTRAINT `FK_plugin_created_by` FOREIGN KEY (`created_by`) REFERENCES `sys_sec_user` (`oid`),
  CONSTRAINT `FK_plugin_deleted_by` FOREIGN KEY (`deleted_by`) REFERENCES `sys_sec_user` (`oid`),
  CONSTRAINT `FK_plugin_last_modified_by` FOREIGN KEY (`last_modified_by`) REFERENCES `sys_sec_user` (`oid`),
  CONSTRAINT `FK_plugin_type_id` FOREIGN KEY (`type_id`) REFERENCES `plugin_type` (`oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/*Data for the table `plugin` */

/*Table structure for table `plugin_type` */

DROP TABLE IF EXISTS `plugin_type`;

CREATE TABLE `plugin_type` (
  `oid` binary(16) NOT NULL,
  `name` varchar(100) DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  PRIMARY KEY (`oid`),
  KEY `iGCRecord_plugin_type` (`GCRecord`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/*Data for the table `plugin_type` */

/*Table structure for table `project` */

DROP TABLE IF EXISTS `project`;

CREATE TABLE `project` (
  `oid` binary(16) NOT NULL,
  `name` varchar(30) DEFAULT NULL,
  `description` varchar(200) DEFAULT NULL,
  `start_on` datetime DEFAULT NULL,
  `end_on` datetime DEFAULT NULL,
  `owner_id` binary(16) DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  `last_accessed_date` datetime DEFAULT NULL,
  PRIMARY KEY (`oid`),
  KEY `iGCRecord_Project` (`GCRecord`),
  KEY `iowner_Project` (`owner_id`),
  CONSTRAINT `FK_Project_owner` FOREIGN KEY (`owner_id`) REFERENCES `sys_sec_user` (`oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci AVG_ROW_LENGTH=8192;

/*Data for the table `project` */

insert  into `project`(`oid`,`name`,`description`,`start_on`,`end_on`,`owner_id`,`OptimisticLockField`,`GCRecord`,`last_accessed_date`) values 
('̾�D��KK�P����','Apofrin project',NULL,NULL,NULL,NULL,1,NULL,NULL),
('勳l��B��yхъ�','Leginon',NULL,NULL,NULL,NULL,NULL,NULL,NULL);

/*Table structure for table `sample_grid_type` */

DROP TABLE IF EXISTS `sample_grid_type`;

CREATE TABLE `sample_grid_type` (
  `oid` binary(16) NOT NULL,
  `name` varchar(30) DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  PRIMARY KEY (`oid`),
  KEY `iGCRecord_SampleGridType` (`GCRecord`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

/*Data for the table `sample_grid_type` */

/*Table structure for table `sample_material` */

DROP TABLE IF EXISTS `sample_material`;

CREATE TABLE `sample_material` (
  `oid` binary(16) NOT NULL,
  `session` binary(16) DEFAULT NULL,
  `name` varchar(30) DEFAULT NULL,
  `quantity` decimal(28,8) DEFAULT NULL,
  `note` varchar(150) DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  PRIMARY KEY (`oid`),
  KEY `iGCRecord_SampleMaterial` (`GCRecord`),
  KEY `isession_SampleMaterial` (`session`),
  CONSTRAINT `FK_SampleMaterial_session` FOREIGN KEY (`session`) REFERENCES `msession` (`oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

/*Data for the table `sample_material` */

/*Table structure for table `sample_type` */

DROP TABLE IF EXISTS `sample_type`;

CREATE TABLE `sample_type` (
  `oid` binary(16) NOT NULL,
  `name` varchar(30) DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  PRIMARY KEY (`oid`),
  KEY `iGCRecord_SampleType` (`GCRecord`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

/*Data for the table `sample_type` */

/*Table structure for table `site` */

DROP TABLE IF EXISTS `site`;

CREATE TABLE `site` (
  `oid` binary(16) NOT NULL,
  `name` varchar(30) DEFAULT NULL,
  `address` varchar(150) DEFAULT NULL,
  `manager_id` binary(16) DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  PRIMARY KEY (`oid`),
  KEY `iGCRecord_Site` (`GCRecord`),
  KEY `imanager_Site` (`manager_id`),
  CONSTRAINT `FK_Site_manager` FOREIGN KEY (`manager_id`) REFERENCES `sys_sec_user` (`oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

/*Data for the table `site` */

/*Table structure for table `sys_sec_action_permission` */

DROP TABLE IF EXISTS `sys_sec_action_permission`;

CREATE TABLE `sys_sec_action_permission` (
  `Oid` binary(16) NOT NULL,
  `ActionId` varchar(100) DEFAULT NULL,
  `Role` binary(16) DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  PRIMARY KEY (`Oid`),
  KEY `iGCRecord_sys_sec_action_permission` (`GCRecord`),
  KEY `iRole_sys_sec_action_permission` (`Role`),
  CONSTRAINT `FK_sys_sec_action_permission_Role` FOREIGN KEY (`Role`) REFERENCES `sys_sec_role` (`Oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/*Data for the table `sys_sec_action_permission` */

/*Table structure for table `sys_sec_login_info` */

DROP TABLE IF EXISTS `sys_sec_login_info`;

CREATE TABLE `sys_sec_login_info` (
  `Oid` binary(16) NOT NULL,
  `LoginProviderName` varchar(100) DEFAULT NULL,
  `ProviderUserKey` varchar(100) DEFAULT NULL,
  `User` binary(16) DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  PRIMARY KEY (`Oid`),
  UNIQUE KEY `iLoginProviderNameProviderUserKey_sys_sec_login_info` (`LoginProviderName`,`ProviderUserKey`),
  KEY `iUser_sys_sec_login_info` (`User`),
  CONSTRAINT `FK_sys_sec_login_info_User` FOREIGN KEY (`User`) REFERENCES `sys_sec_user` (`oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/*Data for the table `sys_sec_login_info` */

insert  into `sys_sec_login_info`(`Oid`,`LoginProviderName`,`ProviderUserKey`,`User`,`OptimisticLockField`) values 
('S>%�y\nC��V�v��c','Password','df17eae4-a8ed-437d-9276-fc0705126bf4','����}C�v�k�',0),
('�����E��Dv���8','Password','03f53a35-2d19-466b-90a6-3315141ba34d','5:�-kF��3�M',0);

/*Table structure for table `sys_sec_member_permission` */

DROP TABLE IF EXISTS `sys_sec_member_permission`;

CREATE TABLE `sys_sec_member_permission` (
  `Oid` binary(16) NOT NULL,
  `Members` longtext DEFAULT NULL,
  `ReadState` int(11) DEFAULT NULL,
  `WriteState` int(11) DEFAULT NULL,
  `Criteria` longtext DEFAULT NULL,
  `TypePermissionObject` binary(16) DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  PRIMARY KEY (`Oid`),
  KEY `iGCRecord_sys_sec_member_permission` (`GCRecord`),
  KEY `iTypePermissionObject_sys_sec_member_permission` (`TypePermissionObject`),
  CONSTRAINT `FK_sys_sec_member_permission_TypePermissionObject` FOREIGN KEY (`TypePermissionObject`) REFERENCES `sys_sec_type_permission` (`Oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/*Data for the table `sys_sec_member_permission` */

insert  into `sys_sec_member_permission`(`Oid`,`Members`,`ReadState`,`WriteState`,`Criteria`,`TypePermissionObject`,`OptimisticLockField`,`GCRecord`) values 
('\0�\'[0._L�����q�','ChangePasswordOnFirstLogon',NULL,1,'[Oid] = CurrentUserId()','��vx|�K�:��d3�n',0,NULL),
('1Mv��q N�l���\r�','StoredPassword',NULL,1,'[Oid] = CurrentUserId()','��vx|�K�:��d3�n',0,NULL);

/*Table structure for table `sys_sec_navigation_permission` */

DROP TABLE IF EXISTS `sys_sec_navigation_permission`;

CREATE TABLE `sys_sec_navigation_permission` (
  `Oid` binary(16) NOT NULL,
  `ItemPath` longtext DEFAULT NULL,
  `NavigateState` int(11) DEFAULT NULL,
  `Role` binary(16) DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  PRIMARY KEY (`Oid`),
  KEY `iGCRecord_sys_sec_navigation_permission` (`GCRecord`),
  KEY `iRole_sys_sec_navigation_permission` (`Role`),
  CONSTRAINT `FK_sys_sec_navigation_permission_Role` FOREIGN KEY (`Role`) REFERENCES `sys_sec_role` (`Oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/*Data for the table `sys_sec_navigation_permission` */

insert  into `sys_sec_navigation_permission`(`Oid`,`ItemPath`,`NavigateState`,`Role`,`OptimisticLockField`,`GCRecord`) values 
('�Z�/v�ON������','Application/NavigationItems/Items/Default/Items/MyDetails',1,'>\n~��DH����.���',0,NULL);

/*Table structure for table `sys_sec_object_permission` */

DROP TABLE IF EXISTS `sys_sec_object_permission`;

CREATE TABLE `sys_sec_object_permission` (
  `Oid` binary(16) NOT NULL,
  `Criteria` longtext DEFAULT NULL,
  `ReadState` int(11) DEFAULT NULL,
  `WriteState` int(11) DEFAULT NULL,
  `DeleteState` int(11) DEFAULT NULL,
  `NavigateState` int(11) DEFAULT NULL,
  `TypePermissionObject` binary(16) DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  PRIMARY KEY (`Oid`),
  KEY `iGCRecord_sys_sec_object_permission` (`GCRecord`),
  KEY `iTypePermissionObject_sys_sec_object_permission` (`TypePermissionObject`),
  CONSTRAINT `FK_sys_sec_object_permission_TypePermissionObject` FOREIGN KEY (`TypePermissionObject`) REFERENCES `sys_sec_type_permission` (`Oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/*Data for the table `sys_sec_object_permission` */

insert  into `sys_sec_object_permission`(`Oid`,`Criteria`,`ReadState`,`WriteState`,`DeleteState`,`NavigateState`,`TypePermissionObject`,`OptimisticLockField`,`GCRecord`) values 
('4es���G��?g{�\Z','[Oid] = CurrentUserId()',1,NULL,NULL,NULL,'��vx|�K�:��d3�n',0,NULL);

/*Table structure for table `sys_sec_role` */

DROP TABLE IF EXISTS `sys_sec_role`;

CREATE TABLE `sys_sec_role` (
  `Oid` binary(16) NOT NULL,
  `Name` varchar(100) DEFAULT NULL,
  `IsAdministrative` bit(1) DEFAULT NULL,
  `CanEditModel` bit(1) DEFAULT NULL,
  `PermissionPolicy` int(11) DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  `ObjectType` int(11) DEFAULT NULL,
  PRIMARY KEY (`Oid`),
  KEY `iGCRecord_sys_sec_role` (`GCRecord`),
  KEY `iObjectType_sys_sec_role` (`ObjectType`),
  CONSTRAINT `FK_sys_sec_role_ObjectType` FOREIGN KEY (`ObjectType`) REFERENCES `xpobjecttype` (`OID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/*Data for the table `sys_sec_role` */

insert  into `sys_sec_role`(`Oid`,`Name`,`IsAdministrative`,`CanEditModel`,`PermissionPolicy`,`OptimisticLockField`,`GCRecord`,`ObjectType`) values 
('>\n~��DH����.���','Default','\0','\0',0,0,NULL,2),
('��!�E�b`B�{','Administrators','','\0',0,0,NULL,2);

/*Table structure for table `sys_sec_type_permission` */

DROP TABLE IF EXISTS `sys_sec_type_permission`;

CREATE TABLE `sys_sec_type_permission` (
  `Oid` binary(16) NOT NULL,
  `Role` binary(16) DEFAULT NULL,
  `TargetType` longtext DEFAULT NULL,
  `ReadState` int(11) DEFAULT NULL,
  `WriteState` int(11) DEFAULT NULL,
  `CreateState` int(11) DEFAULT NULL,
  `DeleteState` int(11) DEFAULT NULL,
  `NavigateState` int(11) DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  PRIMARY KEY (`Oid`),
  KEY `iGCRecord_sys_sec_type_permission` (`GCRecord`),
  KEY `iRole_sys_sec_type_permission` (`Role`),
  CONSTRAINT `FK_sys_sec_type_permission_Role` FOREIGN KEY (`Role`) REFERENCES `sys_sec_role` (`Oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/*Data for the table `sys_sec_type_permission` */

insert  into `sys_sec_type_permission`(`Oid`,`Role`,`TargetType`,`ReadState`,`WriteState`,`CreateState`,`DeleteState`,`NavigateState`,`OptimisticLockField`,`GCRecord`) values 
(')uj����L��%7��N�','>\n~��DH����.���','DevExpress.Persistent.BaseImpl.ModelDifferenceAspect',1,1,1,NULL,NULL,0,NULL),
('�7���D�^\"�Ŝ�\Z','>\n~��DH����.���','Magellon.Security.PermissionPolicyRole',0,NULL,NULL,NULL,NULL,0,NULL),
('��vx|�K�:��d3�n','>\n~��DH����.���','Magellon.Security.User',NULL,NULL,NULL,NULL,NULL,0,NULL),
('̼�W�9pG�U@���*','>\n~��DH����.���','DevExpress.Persistent.BaseImpl.ModelDifference',1,1,1,NULL,NULL,0,NULL);

/*Table structure for table `sys_sec_user` */

DROP TABLE IF EXISTS `sys_sec_user`;

CREATE TABLE `sys_sec_user` (
  `oid` binary(16) NOT NULL,
  `omid` bigint(20) DEFAULT NULL,
  `ouid` varchar(20) DEFAULT NULL,
  `created_date` datetime DEFAULT NULL,
  `created_by` binary(16) DEFAULT NULL,
  `last_modified_date` datetime DEFAULT NULL,
  `last_modified_by` binary(16) DEFAULT NULL,
  `deleted_date` datetime DEFAULT NULL,
  `deleted_by` binary(16) DEFAULT NULL,
  `sync_status` int(11) DEFAULT NULL,
  `version` varchar(10) DEFAULT NULL,
  `PASSWORD` longtext DEFAULT NULL,
  `ChangePasswordOnFirstLogon` bit(1) DEFAULT NULL,
  `USERNAME` varchar(100) DEFAULT NULL,
  `ACTIVE` bit(1) DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  `ObjectType` int(11) DEFAULT NULL,
  `AccessFailedCount` int(11) DEFAULT NULL,
  `LockoutEnd` datetime DEFAULT NULL,
  PRIMARY KEY (`oid`),
  KEY `iGCRecord_sys_sec_user` (`GCRecord`),
  KEY `icreated_by_sys_sec_user` (`created_by`),
  KEY `ilast_modified_by_sys_sec_user` (`last_modified_by`),
  KEY `ideleted_by_sys_sec_user` (`deleted_by`),
  KEY `iObjectType_sys_sec_user` (`ObjectType`),
  CONSTRAINT `FK_sys_sec_user_ObjectType` FOREIGN KEY (`ObjectType`) REFERENCES `xpobjecttype` (`OID`),
  CONSTRAINT `FK_sys_sec_user_created_by` FOREIGN KEY (`created_by`) REFERENCES `sys_sec_user` (`oid`),
  CONSTRAINT `FK_sys_sec_user_deleted_by` FOREIGN KEY (`deleted_by`) REFERENCES `sys_sec_user` (`oid`),
  CONSTRAINT `FK_sys_sec_user_last_modified_by` FOREIGN KEY (`last_modified_by`) REFERENCES `sys_sec_user` (`oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/*Data for the table `sys_sec_user` */

insert  into `sys_sec_user`(`oid`,`omid`,`ouid`,`created_date`,`created_by`,`last_modified_date`,`last_modified_by`,`deleted_date`,`deleted_by`,`sync_status`,`version`,`PASSWORD`,`ChangePasswordOnFirstLogon`,`USERNAME`,`ACTIVE`,`OptimisticLockField`,`GCRecord`,`ObjectType`,`AccessFailedCount`,`LockoutEnd`) values 
('5:�-kF��3�M',0,NULL,'2024-03-06 17:57:56',NULL,NULL,NULL,NULL,NULL,0,NULL,'$2a$11$x26.FIxoWH9zpiYGhpQQIu73XVrikvFbOMUZzJwcxk.EgQYOlq7by','\0','User','',0,NULL,1,0,NULL),
('`I D��TO��T�o�q�',0,NULL,'2023-04-11 10:36:34',NULL,NULL,NULL,NULL,NULL,0,'0','$2a$11$UqoEXjoxz2mDY.IVyipdl.4qTcCiZM40tAYlBWfoBC/UNxe1G.Wxq','\0','Admin','',0,NULL,1,NULL,NULL),
('�D�d�vF���\Z���d',0,NULL,'2023-04-11 10:36:33',NULL,NULL,NULL,NULL,NULL,0,'0','$2a$11$slvef.2LaNj8z6pXZC/BfOlJqpFNhCPeV/o1ea7kghKyKhX4V5ULO','\0','User','',0,NULL,1,NULL,NULL),
('����}C�v�k�',0,NULL,'2024-03-06 17:57:56',NULL,NULL,NULL,NULL,NULL,0,NULL,'$2a$11$OvkZ2rvGFBzYR9Gmach5X.UPJtRCxU1o5yidfJcImWSSFhAQSM77u','\0','Admin','',0,NULL,1,0,NULL);

/*Table structure for table `sys_sec_user_role` */

DROP TABLE IF EXISTS `sys_sec_user_role`;

CREATE TABLE `sys_sec_user_role` (
  `Roles` binary(16) DEFAULT NULL,
  `People` binary(16) DEFAULT NULL,
  `OID` binary(16) NOT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  PRIMARY KEY (`OID`),
  UNIQUE KEY `iRolesPeople_sys_sec_user_role` (`Roles`,`People`),
  KEY `iRoles_sys_sec_user_role` (`Roles`),
  KEY `iPeople_sys_sec_user_role` (`People`),
  CONSTRAINT `FK_sys_sec_user_role_People` FOREIGN KEY (`People`) REFERENCES `sys_sec_user` (`oid`),
  CONSTRAINT `FK_sys_sec_user_role_Roles` FOREIGN KEY (`Roles`) REFERENCES `sys_sec_role` (`Oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/*Data for the table `sys_sec_user_role` */

insert  into `sys_sec_user_role`(`Roles`,`People`,`OID`,`OptimisticLockField`) values 
('>\n~��DH����.���','5:�-kF��3�M','�_ru��F�B:Gx�W�',0),
('��!�E�b`B�{','����}C�v�k�','����2�aJ��rsF�5_',0);

/*Table structure for table `xpobjecttype` */

DROP TABLE IF EXISTS `xpobjecttype`;

CREATE TABLE `xpobjecttype` (
  `OID` int(11) NOT NULL AUTO_INCREMENT,
  `TypeName` varchar(254) DEFAULT NULL,
  `AssemblyName` varchar(254) DEFAULT NULL,
  PRIMARY KEY (`OID`),
  UNIQUE KEY `iTypeName_XPObjectType` (`TypeName`)
) ENGINE=InnoDB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/*Data for the table `xpobjecttype` */


/* Procedure structure for procedure `update_levels` */

/*!50003 DROP PROCEDURE IF EXISTS  `update_levels` */;

DELIMITER $$

/*!50003 CREATE DEFINER=`behdad`@`%` PROCEDURE `update_levels`()
BEGIN
    SET @tlevel = 1;

UPDATE image set level=NULL;

UPDATE image SET level = 0 WHERE parent_id IS NULL;


while  @tlevel < 8 do
    UPDATE image AS child
    JOIN image AS parent ON child.parent_id = parent.oid
    SET child.level = @tlevel + 1
    WHERE parent.level = @tlevel;

    SET @tlevel = @tlevel + 1;
end while;
END */$$
DELIMITER ;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;
