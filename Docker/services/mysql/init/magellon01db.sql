/*
Magellon Database Initialization Script
=======================================
MySQL 8.0+ : Database - magellon01

This script creates:
- All application tables (image, msession, camera, etc.)
- Security tables (sys_sec_*)
- Casbin table (casbin_rule)
- Default admin user (super/behd1d2)
- Default roles and permissions

Usage:
  mysql -u root -p < magellon01db.sql

After running this script, the 'super' user will have full Administrator access.

Version: 2.0
Last Updated: 2025-12-09
*/

/*!40101 SET NAMES utf8mb4 */;
/*!40101 SET SQL_MODE=''*/;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

CREATE DATABASE /*!32312 IF NOT EXISTS*/`magellon01` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci */ /*!80016 DEFAULT ENCRYPTION='N' */;

USE `magellon01`;

-- ============================================================================
-- LOOKUP/REFERENCE TABLES (no foreign key dependencies)
-- ============================================================================

/*Table structure for table `xpobjecttype` */
DROP TABLE IF EXISTS `xpobjecttype`;
CREATE TABLE `xpobjecttype` (
  `OID` INT NOT NULL AUTO_INCREMENT,
  `TypeName` VARCHAR(254) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `AssemblyName` VARCHAR(254) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`OID`),
  UNIQUE KEY `iTypeName_XPObjectType` (`TypeName`)
) ENGINE=INNODB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `xpobjecttype` (`OID`, `TypeName`, `AssemblyName`) VALUES
(1, 'Magellon.Security.User', 'Magellon.Security'),
(2, 'Magellon.Security.PermissionPolicyRole', 'Magellon.Security');

/*Table structure for table `camera` */
DROP TABLE IF EXISTS `camera`;
CREATE TABLE `camera` (
  `oid` BINARY(16) NOT NULL,
  `name` VARCHAR(30) DEFAULT NULL,
  `OptimisticLockField` INT DEFAULT NULL,
  `GCRecord` INT DEFAULT NULL,
  PRIMARY KEY (`oid`),
  KEY `iGCRecord_Camera` (`GCRecord`)
) ENGINE=INNODB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `camera` (`oid`, `name`, `OptimisticLockField`, `GCRecord`) VALUES
(UNHEX('11111111111111111111111111111111'), 'Kasha Lab #1 Cam', NULL, NULL),
(UNHEX('22222222222222222222222222222222'), 'Alpine', NULL, NULL);

/*Table structure for table `microscope` */
DROP TABLE IF EXISTS `microscope`;
CREATE TABLE `microscope` (
  `oid` BINARY(16) NOT NULL,
  `name` VARCHAR(30) DEFAULT NULL,
  `OptimisticLockField` INT DEFAULT NULL,
  `GCRecord` INT DEFAULT NULL,
  PRIMARY KEY (`oid`),
  KEY `iGCRecord_Microscope` (`GCRecord`)
) ENGINE=INNODB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/*Table structure for table `sample_type` */
DROP TABLE IF EXISTS `sample_type`;
CREATE TABLE `sample_type` (
  `oid` BINARY(16) NOT NULL,
  `name` VARCHAR(30) DEFAULT NULL,
  `OptimisticLockField` INT DEFAULT NULL,
  `GCRecord` INT DEFAULT NULL,
  PRIMARY KEY (`oid`),
  KEY `iGCRecord_SampleType` (`GCRecord`)
) ENGINE=INNODB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/*Table structure for table `sample_grid_type` */
DROP TABLE IF EXISTS `sample_grid_type`;
CREATE TABLE `sample_grid_type` (
  `oid` BINARY(16) NOT NULL,
  `name` VARCHAR(30) DEFAULT NULL,
  `OptimisticLockField` INT DEFAULT NULL,
  `GCRecord` INT DEFAULT NULL,
  PRIMARY KEY (`oid`),
  KEY `iGCRecord_SampleGridType` (`GCRecord`)
) ENGINE=INNODB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/*Table structure for table `plugin_type` */
DROP TABLE IF EXISTS `plugin_type`;
CREATE TABLE `plugin_type` (
  `oid` BINARY(16) NOT NULL,
  `name` VARCHAR(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `OptimisticLockField` INT DEFAULT NULL,
  `GCRecord` INT DEFAULT NULL,
  PRIMARY KEY (`oid`),
  KEY `iGCRecord_plugin_type` (`GCRecord`)
) ENGINE=INNODB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/*Table structure for table `image_meta_data_category` */
DROP TABLE IF EXISTS `image_meta_data_category`;
CREATE TABLE `image_meta_data_category` (
  `oid` INT NOT NULL,
  `name` VARCHAR(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `parent_id` INT DEFAULT NULL,
  `OptimisticLockField` INT DEFAULT NULL,
  `GCRecord` INT DEFAULT NULL,
  PRIMARY KEY (`oid`),
  KEY `iGCRecord_image_meta_data_category` (`GCRecord`),
  KEY `iparent_id_image_meta_data_category` (`parent_id`),
  CONSTRAINT `FK_image_meta_data_category_parent_id` FOREIGN KEY (`parent_id`) REFERENCES `image_meta_data_category` (`oid`)
) ENGINE=INNODB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `image_meta_data_category` (`oid`, `name`, `parent_id`, `OptimisticLockField`, `GCRecord`) VALUES
(1, 'FFT', NULL, NULL, NULL),
(2, 'CTF', NULL, NULL, NULL),
(3, 'Frame Alignment', NULL, NULL, NULL),
(4, 'Particle Picking', NULL, NULL, NULL),
(10, 'Other', NULL, NULL, NULL);

-- ============================================================================
-- SECURITY TABLES
-- ============================================================================

/*Table structure for table `sys_sec_role` */
DROP TABLE IF EXISTS `sys_sec_role`;
CREATE TABLE `sys_sec_role` (
  `Oid` BINARY(16) NOT NULL,
  `Name` VARCHAR(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `IsAdministrative` BIT(1) DEFAULT NULL,
  `CanEditModel` BIT(1) DEFAULT NULL,
  `PermissionPolicy` INT DEFAULT NULL,
  `OptimisticLockField` INT DEFAULT NULL,
  `GCRecord` INT DEFAULT NULL,
  `ObjectType` INT DEFAULT NULL,
  PRIMARY KEY (`Oid`),
  KEY `iGCRecord_sys_sec_role` (`GCRecord`),
  KEY `iObjectType_sys_sec_role` (`ObjectType`),
  CONSTRAINT `FK_sys_sec_role_ObjectType` FOREIGN KEY (`ObjectType`) REFERENCES `xpobjecttype` (`OID`)
) ENGINE=INNODB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Fixed UUIDs for roles (using proper hex format)
-- Users role:        AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA
-- Administrator role: BBBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB
INSERT INTO `sys_sec_role` (`Oid`, `Name`, `IsAdministrative`, `CanEditModel`, `PermissionPolicy`, `OptimisticLockField`, `GCRecord`, `ObjectType`) VALUES
(UNHEX('AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'), 'Users', b'0', b'0', 0, 0, NULL, 2),
(UNHEX('BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB'), 'Administrator', b'1', b'0', 0, 0, NULL, 2);

/*Table structure for table `sys_sec_user` */
DROP TABLE IF EXISTS `sys_sec_user`;
CREATE TABLE `sys_sec_user` (
  `oid` BINARY(16) NOT NULL,
  `omid` BIGINT DEFAULT NULL,
  `ouid` VARCHAR(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_date` DATETIME DEFAULT NULL,
  `created_by` BINARY(16) DEFAULT NULL,
  `last_modified_date` DATETIME DEFAULT NULL,
  `last_modified_by` BINARY(16) DEFAULT NULL,
  `deleted_date` DATETIME DEFAULT NULL,
  `deleted_by` BINARY(16) DEFAULT NULL,
  `sync_status` INT DEFAULT NULL,
  `version` VARCHAR(10) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `PASSWORD` LONGTEXT COLLATE utf8mb4_unicode_ci,
  `ChangePasswordOnFirstLogon` BIT(1) DEFAULT NULL,
  `USERNAME` VARCHAR(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ACTIVE` BIT(1) DEFAULT NULL,
  `OptimisticLockField` INT DEFAULT NULL,
  `GCRecord` INT DEFAULT NULL,
  `ObjectType` INT DEFAULT NULL,
  `AccessFailedCount` INT DEFAULT NULL,
  `LockoutEnd` DATETIME DEFAULT NULL,
  PRIMARY KEY (`oid`),
  KEY `iGCRecord_sys_sec_user` (`GCRecord`),
  KEY `icreated_by_sys_sec_user` (`created_by`),
  KEY `ilast_modified_by_sys_sec_user` (`last_modified_by`),
  KEY `ideleted_by_sys_sec_user` (`deleted_by`),
  KEY `iObjectType_sys_sec_user` (`ObjectType`),
  CONSTRAINT `FK_sys_sec_user_ObjectType` FOREIGN KEY (`ObjectType`) REFERENCES `xpobjecttype` (`OID`)
) ENGINE=INNODB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Default admin user: super / behd1d2 (bcrypt hashed)
-- User UUID: CCCCCCCC-CCCC-CCCC-CCCC-CCCCCCCCCCCC
INSERT INTO `sys_sec_user` (`oid`, `omid`, `ouid`, `created_date`, `created_by`, `last_modified_date`, `last_modified_by`, `deleted_date`, `deleted_by`, `sync_status`, `version`, `PASSWORD`, `ChangePasswordOnFirstLogon`, `USERNAME`, `ACTIVE`, `OptimisticLockField`, `GCRecord`, `ObjectType`, `AccessFailedCount`, `LockoutEnd`) VALUES
(UNHEX('CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC'), 0, NULL, NOW(), NULL, NULL, NULL, NULL, NULL, 0, '0', '$2a$11$UqoEXjoxz2mDY.IVyipdl.4qTcCiZM40tAYlBWfoBC/UNxe1G.Wxq', b'0', 'super', b'1', 0, NULL, 1, NULL, NULL);

/*Table structure for table `sys_sec_user_role` */
DROP TABLE IF EXISTS `sys_sec_user_role`;
CREATE TABLE `sys_sec_user_role` (
  `Roles` BINARY(16) DEFAULT NULL,
  `People` BINARY(16) DEFAULT NULL,
  `OID` BINARY(16) NOT NULL,
  `OptimisticLockField` INT DEFAULT NULL,
  PRIMARY KEY (`OID`),
  UNIQUE KEY `iRolesPeople_sys_sec_user_role` (`Roles`,`People`),
  KEY `iRoles_sys_sec_user_role` (`Roles`),
  KEY `iPeople_sys_sec_user_role` (`People`),
  CONSTRAINT `FK_sys_sec_user_role_People` FOREIGN KEY (`People`) REFERENCES `sys_sec_user` (`oid`),
  CONSTRAINT `FK_sys_sec_user_role_Roles` FOREIGN KEY (`Roles`) REFERENCES `sys_sec_role` (`Oid`)
) ENGINE=INNODB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Assign 'super' user to both Users and Administrator roles
INSERT INTO `sys_sec_user_role` (`Roles`, `People`, `OID`, `OptimisticLockField`) VALUES
(UNHEX('AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'), UNHEX('CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC'), UNHEX('DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD'), 0),
(UNHEX('BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB'), UNHEX('CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC'), UNHEX('EEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE'), 0);

/*Table structure for table `sys_sec_type_permission` */
DROP TABLE IF EXISTS `sys_sec_type_permission`;
CREATE TABLE `sys_sec_type_permission` (
  `Oid` BINARY(16) NOT NULL,
  `Role` BINARY(16) DEFAULT NULL,
  `TargetType` LONGTEXT COLLATE utf8mb4_unicode_ci,
  `ReadState` INT DEFAULT NULL,
  `WriteState` INT DEFAULT NULL,
  `CreateState` INT DEFAULT NULL,
  `DeleteState` INT DEFAULT NULL,
  `NavigateState` INT DEFAULT NULL,
  `OptimisticLockField` INT DEFAULT NULL,
  `GCRecord` INT DEFAULT NULL,
  PRIMARY KEY (`Oid`),
  KEY `iGCRecord_sys_sec_type_permission` (`GCRecord`),
  KEY `iRole_sys_sec_type_permission` (`Role`),
  CONSTRAINT `FK_sys_sec_type_permission_Role` FOREIGN KEY (`Role`) REFERENCES `sys_sec_role` (`Oid`)
) ENGINE=INNODB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Type permissions for Administrator role
INSERT INTO `sys_sec_type_permission` (`Oid`, `Role`, `TargetType`, `ReadState`, `WriteState`, `CreateState`, `DeleteState`, `NavigateState`, `OptimisticLockField`, `GCRecord`) VALUES
(UNHEX('11111111000000000000000000000001'), UNHEX('BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB'), 'msession', 1, 1, 1, 0, 1, 0, NULL),
(UNHEX('11111111000000000000000000000002'), UNHEX('BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB'), 'image', 1, 1, 1, 0, 0, 0, NULL);

/*Table structure for table `sys_sec_action_permission` */
DROP TABLE IF EXISTS `sys_sec_action_permission`;
CREATE TABLE `sys_sec_action_permission` (
  `Oid` binary(16) NOT NULL,
  `ActionId` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `Role` binary(16) DEFAULT NULL,
  `OptimisticLockField` int DEFAULT NULL,
  `GCRecord` int DEFAULT NULL,
  PRIMARY KEY (`Oid`),
  KEY `iGCRecord_sys_sec_action_permission` (`GCRecord`),
  KEY `iRole_sys_sec_action_permission` (`Role`),
  CONSTRAINT `FK_sys_sec_action_permission_Role` FOREIGN KEY (`Role`) REFERENCES `sys_sec_role` (`Oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Action permissions for Administrator role
INSERT INTO `sys_sec_action_permission` (`Oid`, `ActionId`, `Role`, `OptimisticLockField`, `GCRecord`) VALUES
(UNHEX('22222222000000000000000000000001'), 'CreateSession', UNHEX('BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB'), 0, NULL);

/*Table structure for table `sys_sec_navigation_permission` */
DROP TABLE IF EXISTS `sys_sec_navigation_permission`;
CREATE TABLE `sys_sec_navigation_permission` (
  `Oid` binary(16) NOT NULL,
  `ItemPath` longtext COLLATE utf8mb4_unicode_ci,
  `NavigateState` int DEFAULT NULL,
  `Role` binary(16) DEFAULT NULL,
  `OptimisticLockField` int DEFAULT NULL,
  `GCRecord` int DEFAULT NULL,
  PRIMARY KEY (`Oid`),
  KEY `iGCRecord_sys_sec_navigation_permission` (`GCRecord`),
  KEY `iRole_sys_sec_navigation_permission` (`Role`),
  CONSTRAINT `FK_sys_sec_navigation_permission_Role` FOREIGN KEY (`Role`) REFERENCES `sys_sec_role` (`Oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Navigation permissions for Users role
INSERT INTO `sys_sec_navigation_permission` (`Oid`, `ItemPath`, `NavigateState`, `Role`, `OptimisticLockField`, `GCRecord`) VALUES
(UNHEX('33333333000000000000000000000001'), 'Application/NavigationItems/Items/Default/Items/MyDetails', 1, UNHEX('AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'), 0, NULL);

/*Table structure for table `sys_sec_object_permission` */
DROP TABLE IF EXISTS `sys_sec_object_permission`;
CREATE TABLE `sys_sec_object_permission` (
  `Oid` binary(16) NOT NULL,
  `Criteria` longtext COLLATE utf8mb4_unicode_ci,
  `ReadState` int DEFAULT NULL,
  `WriteState` int DEFAULT NULL,
  `DeleteState` int DEFAULT NULL,
  `NavigateState` int DEFAULT NULL,
  `TypePermissionObject` binary(16) DEFAULT NULL,
  `OptimisticLockField` int DEFAULT NULL,
  `GCRecord` int DEFAULT NULL,
  PRIMARY KEY (`Oid`),
  KEY `iGCRecord_sys_sec_object_permission` (`GCRecord`),
  KEY `iTypePermissionObject_sys_sec_object_permission` (`TypePermissionObject`),
  CONSTRAINT `FK_sys_sec_object_permission_TypePermissionObject` FOREIGN KEY (`TypePermissionObject`) REFERENCES `sys_sec_type_permission` (`Oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/*Table structure for table `sys_sec_member_permission` */
DROP TABLE IF EXISTS `sys_sec_member_permission`;
CREATE TABLE `sys_sec_member_permission` (
  `Oid` binary(16) NOT NULL,
  `Members` longtext COLLATE utf8mb4_unicode_ci,
  `ReadState` int DEFAULT NULL,
  `WriteState` int DEFAULT NULL,
  `Criteria` longtext COLLATE utf8mb4_unicode_ci,
  `TypePermissionObject` binary(16) DEFAULT NULL,
  `OptimisticLockField` int DEFAULT NULL,
  `GCRecord` int DEFAULT NULL,
  PRIMARY KEY (`Oid`),
  KEY `iGCRecord_sys_sec_member_permission` (`GCRecord`),
  KEY `iTypePermissionObject_sys_sec_member_permission` (`TypePermissionObject`),
  CONSTRAINT `FK_sys_sec_member_permission_TypePermissionObject` FOREIGN KEY (`TypePermissionObject`) REFERENCES `sys_sec_type_permission` (`Oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/*Table structure for table `sys_sec_login_info` */
DROP TABLE IF EXISTS `sys_sec_login_info`;
CREATE TABLE `sys_sec_login_info` (
  `Oid` binary(16) NOT NULL,
  `LoginProviderName` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `ProviderUserKey` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `User` binary(16) DEFAULT NULL,
  `OptimisticLockField` int DEFAULT NULL,
  PRIMARY KEY (`Oid`),
  UNIQUE KEY `iLoginProviderNameProviderUserKey_sys_sec_login_info` (`LoginProviderName`,`ProviderUserKey`),
  KEY `iUser_sys_sec_login_info` (`User`),
  CONSTRAINT `FK_sys_sec_login_info_User` FOREIGN KEY (`User`) REFERENCES `sys_sec_user` (`oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- CASBIN TABLE (for authorization policies)
-- ============================================================================

DROP TABLE IF EXISTS `casbin_rule`;
CREATE TABLE `casbin_rule` (
  `id` int NOT NULL AUTO_INCREMENT,
  `ptype` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `v0` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `v1` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `v2` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `v3` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `v4` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `v5` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_casbin_rule` (`ptype`, `v0`, `v1`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Role assignments (g policies): user_id -> role_name
-- super user (CCCCCCCC...) gets both Users and Administrator roles
INSERT INTO `casbin_rule` (`ptype`, `v0`, `v1`, `v2`, `v3`, `v4`, `v5`) VALUES
('g', 'cccccccc-cccc-cccc-cccc-cccccccccccc', 'Users', NULL, NULL, NULL, NULL),
('g', 'cccccccc-cccc-cccc-cccc-cccccccccccc', 'Administrator', NULL, NULL, NULL, NULL);

-- Permission policies (p policies): role, resource, action, effect
-- Administrator role permissions
INSERT INTO `casbin_rule` (`ptype`, `v0`, `v1`, `v2`, `v3`, `v4`, `v5`) VALUES
('p', 'Administrator', 'msession:*', 'read', 'allow', NULL, NULL),
('p', 'Administrator', 'msession:*', 'write', 'allow', NULL, NULL),
('p', 'Administrator', 'msession:*', 'create', 'allow', NULL, NULL),
('p', 'Administrator', 'msession:*', 'navigate', 'allow', NULL, NULL),
('p', 'Administrator', 'image:*', 'read', 'allow', NULL, NULL),
('p', 'Administrator', 'image:*', 'write', 'allow', NULL, NULL),
('p', 'Administrator', 'image:*', 'create', 'allow', NULL, NULL),
('p', 'Administrator', 'action:CreateSession', 'execute', 'allow', NULL, NULL);

-- Users role permissions
INSERT INTO `casbin_rule` (`ptype`, `v0`, `v1`, `v2`, `v3`, `v4`, `v5`) VALUES
('p', 'Users', 'navigation:Application/NavigationItems/Items/Default/Items/MyDetails', 'navigate', 'allow', NULL, NULL);

-- ============================================================================
-- APPLICATION TABLES
-- ============================================================================

/*Table structure for table `site` */
DROP TABLE IF EXISTS `site`;
CREATE TABLE `site` (
  `oid` binary(16) NOT NULL,
  `name` varchar(30) DEFAULT NULL,
  `address` varchar(150) DEFAULT NULL,
  `manager_id` binary(16) DEFAULT NULL,
  `OptimisticLockField` int DEFAULT NULL,
  `GCRecord` int DEFAULT NULL,
  PRIMARY KEY (`oid`),
  KEY `iGCRecord_Site` (`GCRecord`),
  KEY `imanager_Site` (`manager_id`),
  CONSTRAINT `FK_Site_manager` FOREIGN KEY (`manager_id`) REFERENCES `sys_sec_user` (`oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/*Table structure for table `project` */
DROP TABLE IF EXISTS `project`;
CREATE TABLE `project` (
  `oid` binary(16) NOT NULL,
  `name` varchar(30) DEFAULT NULL,
  `description` varchar(200) DEFAULT NULL,
  `start_on` datetime DEFAULT NULL,
  `end_on` datetime DEFAULT NULL,
  `owner_id` binary(16) DEFAULT NULL,
  `OptimisticLockField` int DEFAULT NULL,
  `GCRecord` int DEFAULT NULL,
  `last_accessed_date` datetime DEFAULT NULL,
  PRIMARY KEY (`oid`),
  KEY `iGCRecord_Project` (`GCRecord`),
  KEY `iowner_Project` (`owner_id`),
  CONSTRAINT `FK_Project_owner` FOREIGN KEY (`owner_id`) REFERENCES `sys_sec_user` (`oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `project` (`oid`, `name`, `description`, `start_on`, `end_on`, `owner_id`, `OptimisticLockField`, `GCRecord`, `last_accessed_date`) VALUES
(UNHEX('44444444444444444444444444444444'), 'Default Project', NULL, NULL, NULL, NULL, 1, NULL, NULL),
(UNHEX('55555555555555555555555555555555'), 'Leginon', NULL, NULL, NULL, NULL, NULL, NULL, NULL);

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
  `sample_sequence` text,
  `sample_procedure` longtext,
  `OptimisticLockField` int DEFAULT NULL,
  `GCRecord` int DEFAULT NULL,
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/*Table structure for table `atlas` */
DROP TABLE IF EXISTS `atlas`;
CREATE TABLE `atlas` (
  `oid` binary(16) NOT NULL,
  `name` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `meta` longtext COLLATE utf8mb4_unicode_ci,
  `OptimisticLockField` int DEFAULT NULL,
  `GCRecord` int DEFAULT NULL,
  `session_id` binary(16) DEFAULT NULL,
  PRIMARY KEY (`oid`),
  KEY `iGCRecord_Atlas` (`GCRecord`),
  KEY `imsession_id_Atlas` (`session_id`),
  CONSTRAINT `FK_Atlas_msession_id` FOREIGN KEY (`session_id`) REFERENCES `msession` (`oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/*Table structure for table `image` */
DROP TABLE IF EXISTS `image`;
CREATE TABLE `image` (
  `oid` binary(16) NOT NULL,
  `name` varchar(100) DEFAULT NULL,
  `frame_name` varchar(100) DEFAULT NULL,
  `path` varchar(300) DEFAULT NULL,
  `parent_id` binary(16) DEFAULT NULL,
  `session_id` binary(16) DEFAULT NULL,
  `magnification` bigint DEFAULT NULL,
  `dose` double DEFAULT NULL,
  `focus` decimal(28,8) DEFAULT NULL,
  `defocus` decimal(28,8) DEFAULT NULL,
  `spot_size` bigint DEFAULT NULL,
  `intensity` decimal(28,8) DEFAULT NULL,
  `shift_x` decimal(28,8) DEFAULT NULL,
  `shift_y` decimal(28,8) DEFAULT NULL,
  `beam_shift_x` decimal(28,8) DEFAULT NULL,
  `beam_shift_y` decimal(28,8) DEFAULT NULL,
  `reset_focus` bigint DEFAULT NULL,
  `screen_current` bigint DEFAULT NULL,
  `beam_bank` varchar(150) DEFAULT NULL,
  `condenser_x` decimal(28,8) DEFAULT NULL,
  `condenser_y` decimal(28,8) DEFAULT NULL,
  `objective_x` decimal(28,8) DEFAULT NULL,
  `objective_y` decimal(28,8) DEFAULT NULL,
  `dimension_x` bigint DEFAULT NULL,
  `dimension_y` bigint DEFAULT NULL,
  `binning_x` bigint DEFAULT NULL,
  `binning_y` bigint DEFAULT NULL,
  `offset_x` bigint DEFAULT NULL,
  `offset_y` bigint DEFAULT NULL,
  `exposure_time` decimal(28,8) DEFAULT NULL,
  `exposure_type` bigint DEFAULT NULL,
  `pixel_size_x` decimal(28,8) DEFAULT NULL,
  `pixel_size_y` decimal(28,8) DEFAULT NULL,
  `energy_filtered` bit(1) DEFAULT NULL,
  `OptimisticLockField` int DEFAULT NULL,
  `GCRecord` int DEFAULT NULL,
  `previous_id` bigint DEFAULT NULL,
  `pixel_size` double DEFAULT NULL,
  `level` int DEFAULT NULL,
  `atlas_delta_row` double DEFAULT NULL,
  `atlas_delta_column` double DEFAULT NULL,
  `atlas_dimxy` double DEFAULT NULL,
  `metadata` longtext,
  `stage_alpha_tilt` double DEFAULT NULL,
  `stage_x` double DEFAULT NULL,
  `stage_y` double DEFAULT NULL,
  `atlas_id` binary(16) DEFAULT NULL,
  `last_accessed_date` datetime DEFAULT NULL,
  `frame_count` int DEFAULT NULL,
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/*Table structure for table `sample_material` */
DROP TABLE IF EXISTS `sample_material`;
CREATE TABLE `sample_material` (
  `oid` binary(16) NOT NULL,
  `session` binary(16) DEFAULT NULL,
  `name` varchar(30) DEFAULT NULL,
  `quantity` decimal(28,8) DEFAULT NULL,
  `note` varchar(150) DEFAULT NULL,
  `OptimisticLockField` int DEFAULT NULL,
  `GCRecord` int DEFAULT NULL,
  PRIMARY KEY (`oid`),
  KEY `iGCRecord_SampleMaterial` (`GCRecord`),
  KEY `isession_SampleMaterial` (`session`),
  CONSTRAINT `FK_SampleMaterial_session` FOREIGN KEY (`session`) REFERENCES `msession` (`oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/*Table structure for table `plugin` */
DROP TABLE IF EXISTS `plugin`;
CREATE TABLE `plugin` (
  `oid` binary(16) NOT NULL,
  `omid` bigint DEFAULT NULL,
  `ouid` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_date` datetime DEFAULT NULL,
  `created_by` binary(16) DEFAULT NULL,
  `last_modified_date` datetime DEFAULT NULL,
  `last_modified_by` binary(16) DEFAULT NULL,
  `deleted_date` datetime DEFAULT NULL,
  `deleted_by` binary(16) DEFAULT NULL,
  `sync_status` int DEFAULT NULL,
  `version` varchar(10) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `name` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `author` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `copyright` text COLLATE utf8mb4_unicode_ci,
  `type_id` binary(16) DEFAULT NULL,
  `status_id` int DEFAULT NULL,
  `coresponding` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `documentation` longtext COLLATE utf8mb4_unicode_ci,
  `website` varchar(250) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `input_json` longtext COLLATE utf8mb4_unicode_ci,
  `OptimisticLockField` int DEFAULT NULL,
  `GCRecord` int DEFAULT NULL,
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

/*Table structure for table `pipeline` */
DROP TABLE IF EXISTS `pipeline`;
CREATE TABLE `pipeline` (
  `oid` binary(16) NOT NULL,
  `omid` bigint DEFAULT NULL,
  `ouid` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_date` datetime DEFAULT NULL,
  `created_by` binary(16) DEFAULT NULL,
  `last_modified_date` datetime DEFAULT NULL,
  `last_modified_by` binary(16) DEFAULT NULL,
  `deleted_date` datetime DEFAULT NULL,
  `deleted_by` binary(16) DEFAULT NULL,
  `sync_status` int DEFAULT NULL,
  `version` varchar(10) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `name` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `data` longtext COLLATE utf8mb4_unicode_ci,
  `data_json` longtext COLLATE utf8mb4_unicode_ci,
  `Description` longtext COLLATE utf8mb4_unicode_ci,
  `OptimisticLockField` int DEFAULT NULL,
  `GCRecord` int DEFAULT NULL,
  PRIMARY KEY (`oid`),
  KEY `iGCRecord_pipeline` (`GCRecord`),
  KEY `icreated_by_pipeline` (`created_by`),
  KEY `ilast_modified_by_pipeline` (`last_modified_by`),
  KEY `ideleted_by_pipeline` (`deleted_by`),
  CONSTRAINT `FK_pipeline_created_by` FOREIGN KEY (`created_by`) REFERENCES `sys_sec_user` (`oid`),
  CONSTRAINT `FK_pipeline_deleted_by` FOREIGN KEY (`deleted_by`) REFERENCES `sys_sec_user` (`oid`),
  CONSTRAINT `FK_pipeline_last_modified_by` FOREIGN KEY (`last_modified_by`) REFERENCES `sys_sec_user` (`oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/*Table structure for table `pipeline_item` */
DROP TABLE IF EXISTS `pipeline_item`;
CREATE TABLE `pipeline_item` (
  `oid` binary(16) NOT NULL,
  `omid` bigint DEFAULT NULL,
  `ouid` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_date` datetime DEFAULT NULL,
  `created_by` binary(16) DEFAULT NULL,
  `last_modified_date` datetime DEFAULT NULL,
  `last_modified_by` binary(16) DEFAULT NULL,
  `deleted_date` datetime DEFAULT NULL,
  `deleted_by` binary(16) DEFAULT NULL,
  `sync_status` int DEFAULT NULL,
  `version` varchar(10) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `name` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `pipeline_id` binary(16) DEFAULT NULL,
  `plugin_id` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `status` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `OptimisticLockField` int DEFAULT NULL,
  `GCRecord` int DEFAULT NULL,
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

/*Table structure for table `image_job` */
DROP TABLE IF EXISTS `image_job`;
CREATE TABLE `image_job` (
  `oid` binary(16) NOT NULL,
  `name` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `description` text COLLATE utf8mb4_unicode_ci,
  `created_date` datetime DEFAULT NULL,
  `start_date` datetime DEFAULT NULL,
  `end_date` datetime DEFAULT NULL,
  `user_id` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `project_id` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `msession_id` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `status_id` smallint unsigned DEFAULT NULL,
  `type_id` smallint unsigned DEFAULT NULL,
  `data` longtext COLLATE utf8mb4_unicode_ci,
  `data_json` longtext COLLATE utf8mb4_unicode_ci,
  `processed_json` longtext COLLATE utf8mb4_unicode_ci,
  `output_directory` varchar(250) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `direction` smallint unsigned DEFAULT NULL,
  `image_selection_criteria` text COLLATE utf8mb4_unicode_ci,
  `pipeline_id` binary(16) DEFAULT NULL,
  `OptimisticLockField` int DEFAULT NULL,
  `GCRecord` int DEFAULT NULL,
  PRIMARY KEY (`oid`),
  KEY `iGCRecord_image_job` (`GCRecord`),
  KEY `ipipeline_id_image_job` (`pipeline_id`),
  CONSTRAINT `FK_image_job_pipeline_id` FOREIGN KEY (`pipeline_id`) REFERENCES `pipeline` (`oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/*Table structure for table `image_job_task` */
DROP TABLE IF EXISTS `image_job_task`;
CREATE TABLE `image_job_task` (
  `oid` binary(16) NOT NULL,
  `job_id` binary(16) DEFAULT NULL,
  `image_id` binary(16) DEFAULT NULL,
  `status_id` smallint unsigned DEFAULT NULL,
  `type_id` smallint unsigned DEFAULT NULL,
  `data` longtext COLLATE utf8mb4_unicode_ci,
  `data_json` longtext COLLATE utf8mb4_unicode_ci,
  `processed_json` longtext COLLATE utf8mb4_unicode_ci,
  `pipeline_item_id` binary(16) DEFAULT NULL,
  `OptimisticLockField` int DEFAULT NULL,
  `GCRecord` int DEFAULT NULL,
  `stage` int DEFAULT NULL,
  `image_name` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `image_path` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `frame_name` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `frame_path` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`oid`),
  KEY `iGCRecord_image_job_task` (`GCRecord`),
  KEY `ijob_id_image_job_task` (`job_id`),
  KEY `iimage_id_image_job_task` (`image_id`),
  KEY `ipipeline_item_id_image_job_task` (`pipeline_item_id`),
  CONSTRAINT `FK_image_job_task_image_id` FOREIGN KEY (`image_id`) REFERENCES `image` (`oid`),
  CONSTRAINT `FK_image_job_task_job_id` FOREIGN KEY (`job_id`) REFERENCES `image_job` (`oid`),
  CONSTRAINT `FK_image_job_task_pipeline_item_id` FOREIGN KEY (`pipeline_item_id`) REFERENCES `pipeline_item` (`oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/*Table structure for table `image_meta_data` */
DROP TABLE IF EXISTS `image_meta_data`;
CREATE TABLE `image_meta_data` (
  `oid` binary(16) NOT NULL,
  `omid` bigint DEFAULT NULL,
  `ouid` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_date` datetime DEFAULT NULL,
  `created_by` binary(16) DEFAULT NULL,
  `last_modified_date` datetime DEFAULT NULL,
  `last_modified_by` binary(16) DEFAULT NULL,
  `deleted_date` datetime DEFAULT NULL,
  `deleted_by` binary(16) DEFAULT NULL,
  `sync_status` int DEFAULT NULL,
  `version` varchar(10) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `image_id` binary(16) DEFAULT NULL,
  `name` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `alias` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `job_id` binary(16) DEFAULT NULL,
  `task_id` binary(16) DEFAULT NULL,
  `category_id` int DEFAULT NULL,
  `data` longtext COLLATE utf8mb4_unicode_ci,
  `data_json` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin,
  `processed_json` longtext COLLATE utf8mb4_unicode_ci,
  `plugin_id` binary(16) DEFAULT NULL,
  `status_id` int DEFAULT NULL,
  `plugin_type_id` binary(16) DEFAULT NULL,
  `OptimisticLockField` int DEFAULT NULL,
  `GCRecord` int DEFAULT NULL,
  `type` int DEFAULT NULL,
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
  CONSTRAINT `FK_image_meta_data_task_id` FOREIGN KEY (`task_id`) REFERENCES `image_job_task` (`oid`),
  CONSTRAINT `image_meta_data_chk_1` CHECK (json_valid(`data_json`))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- STORED PROCEDURES
-- ============================================================================

DELIMITER $$

DROP PROCEDURE IF EXISTS `update_levels`$$

CREATE PROCEDURE `update_levels`()
BEGIN
    SET @tlevel = 1;

    UPDATE image SET level = NULL;
    UPDATE image SET level = 0 WHERE parent_id IS NULL;

    WHILE @tlevel < 8 DO
        UPDATE image AS child
        JOIN image AS parent ON child.parent_id = parent.oid
        SET child.level = @tlevel + 1
        WHERE parent.level = @tlevel;

        SET @tlevel = @tlevel + 1;
    END WHILE;
END$$

DELIMITER ;

-- ============================================================================
-- RESTORE SETTINGS
-- ============================================================================

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- ============================================================================
-- SETUP COMPLETE
-- ============================================================================
/*
Database setup complete!

Default login credentials:
  Username: super
  Password: behd1d2

The 'super' user has Administrator role with full permissions:
  - msession: read, write, create, navigate
  - image: read, write, create
  - action: CreateSession

No additional scripts need to be run - Casbin policies are pre-populated.
*/
