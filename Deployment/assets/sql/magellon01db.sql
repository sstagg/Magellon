/*
SQLyog Ultimate v13.1.1 (64 bit)
MySQL - 10.5.18-MariaDB-0+deb11u1 : Database - magellon02
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

/*Table structure for table `camera` */

DROP TABLE IF EXISTS `camera`;

CREATE TABLE `camera` (
  `Oid` binary(16) NOT NULL,
  `name` varchar(30) DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  PRIMARY KEY (`Oid`),
  KEY `iGCRecord_Camera` (`GCRecord`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

/*Data for the table `camera` */

insert  into `camera`(`Oid`,`name`,`OptimisticLockField`,`GCRecord`) values 
('?�_dWEb��,�?f��','Kasha Lab #1 Cam',NULL,NULL);

/*Table structure for table `ctfjob` */

DROP TABLE IF EXISTS `ctfjob`;

CREATE TABLE `ctfjob` (
  `Oid` binary(16) NOT NULL,
  `name` varchar(100) DEFAULT NULL,
  `description` text DEFAULT NULL,
  `created_on` datetime DEFAULT NULL,
  `start_on` datetime DEFAULT NULL,
  `end_on` datetime DEFAULT NULL,
  `user_id` binary(16) DEFAULT NULL,
  `project_id` binary(16) DEFAULT NULL,
  `msession_id` binary(16) DEFAULT NULL,
  `status` int(11) DEFAULT NULL,
  `type` int(11) DEFAULT NULL,
  `settings` longtext DEFAULT NULL,
  `cs` decimal(28,8) DEFAULT NULL,
  `path` varchar(255) DEFAULT NULL,
  `output_dir` varchar(100) DEFAULT NULL,
  `direction` smallint(5) unsigned DEFAULT NULL,
  `image_selection_criteria` text DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  PRIMARY KEY (`Oid`),
  KEY `iGCRecord_CtfJob` (`GCRecord`),
  KEY `iuser_id_CtfJob` (`user_id`),
  KEY `iproject_id_CtfJob` (`project_id`),
  KEY `imsession_id_CtfJob` (`msession_id`),
  CONSTRAINT `FK_CtfJob_msession_id` FOREIGN KEY (`msession_id`) REFERENCES `msession` (`Oid`),
  CONSTRAINT `FK_CtfJob_project_id` FOREIGN KEY (`project_id`) REFERENCES `project` (`Oid`),
  CONSTRAINT `FK_CtfJob_user_id` FOREIGN KEY (`user_id`) REFERENCES `sys_sec_party` (`Oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

/*Data for the table `ctfjob` */

/*Table structure for table `ctfjobitem` */

DROP TABLE IF EXISTS `ctfjobitem`;

CREATE TABLE `ctfjobitem` (
  `Oid` binary(16) NOT NULL,
  `job_id` binary(16) DEFAULT NULL,
  `image_id` binary(16) DEFAULT NULL,
  `settings` longtext DEFAULT NULL,
  `status` int(11) DEFAULT NULL,
  `score` decimal(28,8) DEFAULT NULL,
  `defocus1` decimal(28,8) DEFAULT NULL,
  `defocus2` decimal(28,8) DEFAULT NULL,
  `res50` decimal(28,8) DEFAULT NULL,
  `res80` decimal(28,8) DEFAULT NULL,
  `tilt_angle` decimal(28,8) DEFAULT NULL,
  `tilt_axis_angle` decimal(28,8) DEFAULT NULL,
  `phase_shift` decimal(28,8) DEFAULT NULL,
  `angle_astigmatism` decimal(28,8) DEFAULT NULL,
  `package_resolution` decimal(28,8) DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  `steps` int(11) DEFAULT NULL,
  PRIMARY KEY (`Oid`),
  KEY `iGCRecord_CtfJobItem` (`GCRecord`),
  KEY `ijob_id_CtfJobItem` (`job_id`),
  KEY `iimage_id_CtfJobItem` (`image_id`),
  CONSTRAINT `FK_CtfJobItem_image_id` FOREIGN KEY (`image_id`) REFERENCES `image` (`Oid`),
  CONSTRAINT `FK_CtfJobItem_job_id` FOREIGN KEY (`job_id`) REFERENCES `ctfjob` (`Oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

/*Data for the table `ctfjobitem` */

/*Table structure for table `frametransferjob` */

DROP TABLE IF EXISTS `frametransferjob`;

CREATE TABLE `frametransferjob` (
  `Oid` binary(16) NOT NULL,
  `name` varchar(100) DEFAULT NULL,
  `description` text DEFAULT NULL,
  `created_on` datetime DEFAULT NULL,
  `start_on` datetime DEFAULT NULL,
  `end_on` datetime DEFAULT NULL,
  `user_id` binary(16) DEFAULT NULL,
  `project_id` binary(16) DEFAULT NULL,
  `msession_id` binary(16) DEFAULT NULL,
  `status` int(11) DEFAULT NULL,
  `type` int(11) DEFAULT NULL,
  `settings` longtext DEFAULT NULL,
  `cs` decimal(28,8) DEFAULT NULL,
  `path` varchar(255) DEFAULT NULL,
  `output_dir` varchar(100) DEFAULT NULL,
  `direction` smallint(5) unsigned DEFAULT NULL,
  `image_selection_criteria` text DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  PRIMARY KEY (`Oid`),
  KEY `iGCRecord_FrameTransferJob` (`GCRecord`),
  KEY `iuser_id_FrameTransferJob` (`user_id`),
  KEY `iproject_id_FrameTransferJob` (`project_id`),
  KEY `imsession_id_FrameTransferJob` (`msession_id`),
  CONSTRAINT `FK_FrameTransferJob_msession_id` FOREIGN KEY (`msession_id`) REFERENCES `msession` (`Oid`),
  CONSTRAINT `FK_FrameTransferJob_project_id` FOREIGN KEY (`project_id`) REFERENCES `project` (`Oid`),
  CONSTRAINT `FK_FrameTransferJob_user_id` FOREIGN KEY (`user_id`) REFERENCES `sys_sec_party` (`Oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

/*Data for the table `frametransferjob` */

/*Table structure for table `frametransferjobitem` */

DROP TABLE IF EXISTS `frametransferjobitem`;

CREATE TABLE `frametransferjobitem` (
  `Oid` binary(16) NOT NULL,
  `job_id` binary(16) DEFAULT NULL,
  `image_id` binary(16) DEFAULT NULL,
  `settings` longtext DEFAULT NULL,
  `status` int(11) DEFAULT NULL,
  `path` text DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  `steps` int(11) DEFAULT NULL,
  PRIMARY KEY (`Oid`),
  KEY `iGCRecord_FrameTransferJobItem` (`GCRecord`),
  KEY `ijob_id_FrameTransferJobItem` (`job_id`),
  KEY `iimage_id_FrameTransferJobItem` (`image_id`),
  CONSTRAINT `FK_FrameTransferJobItem_image_id` FOREIGN KEY (`image_id`) REFERENCES `image` (`Oid`),
  CONSTRAINT `FK_FrameTransferJobItem_job_id` FOREIGN KEY (`job_id`) REFERENCES `frametransferjob` (`Oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

/*Data for the table `frametransferjobitem` */

/*Table structure for table `image` */

DROP TABLE IF EXISTS `image`;

CREATE TABLE `image` (
  `Oid` binary(16) NOT NULL,
  `original` longblob DEFAULT NULL,
  `aligned` longblob DEFAULT NULL,
  `fft` longblob DEFAULT NULL,
  `ctf` longblob DEFAULT NULL,
  `name` varchar(100) DEFAULT NULL,
  `path` varchar(300) DEFAULT NULL,
  `parent_id` binary(16) DEFAULT NULL,
  `session_id` binary(16) DEFAULT NULL,
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
  `old_id` bigint(20) DEFAULT NULL,
  `pixel_size` double DEFAULT NULL,
  `level` int(11) DEFAULT NULL,
  PRIMARY KEY (`Oid`),
  KEY `iGCRecord_Image` (`GCRecord`),
  KEY `iparent_Image` (`parent_id`),
  KEY `isession_Image` (`session_id`),
  CONSTRAINT `FK_Image_parent` FOREIGN KEY (`parent_id`) REFERENCES `image` (`Oid`),
  CONSTRAINT `FK_Image_session` FOREIGN KEY (`session_id`) REFERENCES `msession` (`Oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci AVG_ROW_LENGTH=286;

/*Data for the table `image` */

/*Table structure for table `microscope` */

DROP TABLE IF EXISTS `microscope`;

CREATE TABLE `microscope` (
  `Oid` binary(16) NOT NULL,
  `name` varchar(30) DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  PRIMARY KEY (`Oid`),
  KEY `iGCRecord_Microscope` (`GCRecord`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

/*Data for the table `microscope` */

/*Table structure for table `modeldifference` */

DROP TABLE IF EXISTS `modeldifference`;

CREATE TABLE `modeldifference` (
  `Oid` binary(16) NOT NULL,
  `UserId` varchar(100) DEFAULT NULL,
  `ContextId` varchar(100) DEFAULT NULL,
  `Version` int(11) DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  PRIMARY KEY (`Oid`),
  KEY `iGCRecord_ModelDifference` (`GCRecord`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

/*Data for the table `modeldifference` */

insert  into `modeldifference`(`Oid`,`UserId`,`ContextId`,`Version`,`OptimisticLockField`,`GCRecord`) values 
('�O�@@��o�\"�G|','44204960-8096-4f54-bfc6-548b6ffb71db','Win',0,1,NULL);

/*Table structure for table `modeldifferenceaspect` */

DROP TABLE IF EXISTS `modeldifferenceaspect`;

CREATE TABLE `modeldifferenceaspect` (
  `Oid` binary(16) NOT NULL,
  `Name` varchar(100) DEFAULT NULL,
  `Xml` longtext DEFAULT NULL,
  `Owner` binary(16) DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  PRIMARY KEY (`Oid`),
  KEY `iGCRecord_ModelDifferenceAspect` (`GCRecord`),
  KEY `iOwner_ModelDifferenceAspect` (`Owner`),
  CONSTRAINT `FK_ModelDifferenceAspect_Owner` FOREIGN KEY (`Owner`) REFERENCES `modeldifference` (`Oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

/*Data for the table `modeldifferenceaspect` */

insert  into `modeldifferenceaspect`(`Oid`,`Name`,`Xml`,`Owner`,`OptimisticLockField`,`GCRecord`) values 
('�eӫ���@�6���85','','<?xml version=\"1.0\" encoding=\"utf-8\"?>\r\n<Application>\r\n  <Options DocumentManagerState=\"PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0idXRmLTgiPz4NCjxEb2N1bWVudE1hbmFnZXJTdGF0ZSB4bWxuczp4c2k9Imh0dHA6Ly93d3cudzMub3JnLzIwMDEvWE1MU2NoZW1hLWluc3RhbmNlIiB4bWxuczp4c2Q9Imh0dHA6Ly93d3cudzMub3JnLzIwMDEvWE1MU2NoZW1hIj4NCiAgPERvY3VtZW50RGVzY3JpcHRpb25zPg0KICAgIDxEb2N1bWVudERlc2NyaXB0aW9uPg0KICAgICAgPFNlcmlhbGl6ZWRDb250cm9sPlZpZXdJRD1Qcm9qZWN0X0xpc3RWaWV3JmFtcDtPYmplY3RLZXk9JmFtcDtTY3JvbGxQb3NpdGlvbj0mYW1wO09iamVjdENsYXNzTmFtZT1vcmcubWFnZWxsb24ucHJvamVjdC5Qcm9qZWN0PC9TZXJpYWxpemVkQ29udHJvbD4NCiAgICAgIDxJbWFnZU5hbWU+UHJvamVjdDwvSW1hZ2VOYW1lPg0KICAgICAgPENhcHRpb24+UHJvamVjdDwvQ2FwdGlvbj4NCiAgICAgIDxDb250cm9sTmFtZT40Y2MyZDU3NC04YWQxLTRjMDEtYTE5My0zMWNiODhlYWVkYzM8L0NvbnRyb2xOYW1lPg0KICAgIDwvRG9jdW1lbnREZXNjcmlwdGlvbj4NCiAgICA8RG9jdW1lbnREZXNjcmlwdGlvbj4NCiAgICAgIDxTZXJpYWxpemVkQ29udHJvbD5WaWV3SUQ9UHJvamVjdF9EZXRhaWxWaWV3JmFtcDtPYmplY3RLZXk9NDQ5YmJlY2MtYzk5YS00YjRiLTk3NTAtY2ZmODg3MDViNzAxJmFtcDtTY3JvbGxQb3NpdGlvbj0mYW1wO09iamVjdENsYXNzTmFtZT1vcmcubWFnZWxsb24ucHJvamVjdC5Qcm9qZWN0JmFtcDttb2RlPUVkaXQ8L1NlcmlhbGl6ZWRDb250cm9sPg0KICAgICAgPEltYWdlTmFtZT5Qcm9qZWN0PC9JbWFnZU5hbWU+DQogICAgICA8Q2FwdGlvbj5BcG9mcmluIHByb2plY3QgLSBQcm9qZWN0PC9DYXB0aW9uPg0KICAgICAgPENvbnRyb2xOYW1lPmFhNGY3NGI4LTJkMjEtNDQ5Zi04N2UyLTY0MzBjODE5Yzc2ZTwvQ29udHJvbE5hbWU+DQogICAgPC9Eb2N1bWVudERlc2NyaXB0aW9uPg0KICAgIDxEb2N1bWVudERlc2NyaXB0aW9uPg0KICAgICAgPFNlcmlhbGl6ZWRDb250cm9sPlZpZXdJRD1NU2Vzc2lvbl9EZXRhaWxWaWV3JmFtcDtPYmplY3RLZXk9ZDYzNzQwZTUtMGExNy00YTFmLTk2ZTktNjllN2ZlYTM0Mjg1JmFtcDtTY3JvbGxQb3NpdGlvbj0mYW1wO09iamVjdENsYXNzTmFtZT1vcmcubWFnZWxsb24ucHJvamVjdC5NU2Vzc2lvbiZhbXA7bW9kZT1FZGl0PC9TZXJpYWxpemVkQ29udHJvbD4NCiAgICAgIDxJbWFnZU5hbWU+U2Vzc2lvbjwvSW1hZ2VOYW1lPg0KICAgICAgPENhcHRpb24+U2Vzc2lvbjwvQ2FwdGlvbj4NCiAgICAgIDxDb250cm9sTmFtZT4wY2Y3ZjIxMi05NDVkLTQyY2ItODQyZC03MWFjMDdkYjgxNmI8L0NvbnRyb2xOYW1lPg0KICAgIDwvRG9jdW1lbnREZXNjcmlwdGlvbj4NCiAgICA8RG9jdW1lbnREZXNjcmlwdGlvbj4NCiAgICAgIDxTZXJpYWxpemVkQ29udHJvbD5WaWV3SUQ9SW1hZ2VfTGlzdFZpZXcmYW1wO09iamVjdEtleT0mYW1wO1Njcm9sbFBvc2l0aW9uPSZhbXA7T2JqZWN0Q2xhc3NOYW1lPW9yZy5tYWdlbGxvbi5wcm9qZWN0LkltYWdlPC9TZXJpYWxpemVkQ29udHJvbD4NCiAgICAgIDxJbWFnZU5hbWU+SW1hZ2U8L0ltYWdlTmFtZT4NCiAgICAgIDxDYXB0aW9uPkltYWdlPC9DYXB0aW9uPg0KICAgICAgPENvbnRyb2xOYW1lPjhhNWZhYzNhLWI2ZDMtNDVhNS05YTI5LTRmMWYzMDQ3ZGIxNDwvQ29udHJvbE5hbWU+DQogICAgPC9Eb2N1bWVudERlc2NyaXB0aW9uPg0KICA8L0RvY3VtZW50RGVzY3JpcHRpb25zPg0KICA8Vmlld0xheW91dD5kZ0lBQVBJUG9IZnlBSGZ5QWFCMzhnSjM4Z09oZC9JRUFQSUJvSGZ5QmZLbG9IZnlCbmZ5QjZGMzhnZ0E4Z0NnZC9JSmQvSUtvSGZ5QzNmeUNxQjM4Z3p5QUtCMzhnMTM4Z3FnZC9JT2QvSUtvSGZ5RDNmeUVLRjM4aEVBOGdDaGQvSVNBUElBb1hmeUV3RHlBS0YzOGhUeUIvSUhvWGZ5RlFEeURLQjM4aFozOGhlZ2QvSVlvS0IzOGhueUFLQjM4aHAzOGh1Z2QvSWNvS0YzOGgwQThnQ2dkL0llb0tCMzhoOTM4aUNnZC9JaGQvSWlvSGZ5STZDZ2QvSWtkL0lsb0hmeUpuZnlKNkYzOGlnQThneWdkL0lXZC9JWG9IZnlHS0NnZC9JWjhnR2dkL0lhZC9JYm9IZnlIS0NoZC9JZEFQSUFvSGZ5SHFDZ2QvSWZkL0lnb0hmeUlYZnlJcUIzOGlPZ29IZnlKSGZ5S2FCMzhpWjM4aWVoZC9JcUFQSU1vSGZ5Rm5meUY2QjM4aGlnb0hmeUdmSUNvSGZ5R25meUc2QjM4aHlnb1hmeUhRRHlBS0IzOGg2Z29IZnlIM2Z5SUtCMzhpRjM4aUtnZC9Jam9LQjM4aVIzOGl1Z2QvSW1kL0lub1hmeUxBRHlES0IzOGhaMzhoZWdkL0lZb2FCMzhobnlBNkIzOGhwMzhodWdkL0ljb0tGMzhoMEE4Z0NnZC9JZW9LQjM4aDkzOGkyZ2QvSWhkL0l1b0hmeUk2R2dkL0lrZC9Jdm9IZnlKbmZ5SjZGMzhqQUE4Z2VnZC9JeGQvSXlvSGZ5TXdDZ2QvSUdkL0lIb0hmeUdmSUFvWGZ5TkFEeUFxQjM4aldxQUFBQUFBQUE4RCtnZC9JMmQvSTNvSGZ5SkhmeU9LQjM4aVozOGptaGQvSTZBUElIb0hmeU1YZnlPS0IzOGpOMzhoZWdkL0lHZC9JSG9IZnlHZklBb1hmeU5BRHlBcUIzOGpXcUFBQUFBQUFBOEQrZ2QvSTJkL0kzb0hmeUpIZnlPNkIzOGlaMzhqbWhkL0k4QVBJRm9YZnlIUUR5QUtCMzhqVDBtZ3lnZC9JWjhnQ2dkL0lrZC9JWG9IZnlKbmZ5UGZJK0RpTk1ZWGx2ZFhSV1pYSnphVzl1QUJJalRHRjViM1YwVTJOaGJHVkdZV04wYjNJVlFERXNWMmxrZEdnOU1VQXhMRWhsYVdkb2REMHhFa1J2WTNWdFpXNTBVSEp2Y0dWeWRHbGxjd3ROWVhoVVlXSlhhV1IwYUF0UGNtbGxiblJoZEdsdmJncEliM0pwZW05dWRHRnNGMFJ2WTNWdFpXNTBSM0p2ZFhCUWNtOXdaWEowYVdWekZFVnVZV0pzWlVaeVpXVk1ZWGx2ZFhSTmIyUmxCMFJsWm1GMWJIUVZSVzVoWW14bFUzUnBZMnQ1VTNCc2FYUjBaWEp6R1VOMWMzUnZiVkpsYzJsNlpWcHZibVZVYUdsamEyNWxjM01GVTNSNWJHVVpSbXh2WVhSRWIyTjFiV1Z1ZEhOQmJIZGhlWE5QYmxSdmNCbEdiRzloZEdsdVowUnZZM1Z0Wlc1MFEyOXVkR0ZwYm1WeURVUnZZM1Z0Wlc1MGMwaHZjM1FhVEc5aFpHbHVaMGx1WkdsallYUnZjbEJ5YjNCbGNuUnBaWE1hUkc5amRXMWxiblJUWld4bFkzUnZjbEJ5YjNCbGNuUnBaWE1YVjJsdVpHOTNjMFJwWVd4dloxQnliM0JsY25ScFpYTUZTWFJsYlhNRlNYUmxiVEVLVUdGeVpXNTBUbUZ0WlE1RWIyTjFiV1Z1ZEVkeWIzVndNQXBKYzFObGJHVmpkR1ZrQlVsdVpHVjRDMWRwYm1SdmQxTjBZWFJsQms1dmNtMWhiQVpRYVc1dVpXUUtVSEp2Y0dWeWRHbGxjd3BKYzBac2IyRjBhVzVuQ0V4dlkyRjBhVzl1REVBeExGZzlNRUF4TEZrOU1BUlRhWHBsRlVBeExGZHBaSFJvUFRCQU1TeElaV2xuYUhROU1BaEpjMEZqZEdsMlpRUk9ZVzFsSkRSall6SmtOVGMwTFRoaFpERXROR013TVMxaE1Ua3pMVE14WTJJNE9HVmhaV1JqTXdoVWVYQmxUbUZ0WlFoRWIyTjFiV1Z1ZEFWSmRHVnRNaVJoWVRSbU56UmlPQzB5WkRJeExUUTBPV1l0T0RkbE1pMDJORE13WXpneE9XTTNObVVGU1hSbGJUTWtNR05tTjJZeU1USXRPVFExWkMwME1tTmlMVGcwTW1RdE56RmhZekEzWkdJNE1UWmlCVWwwWlcwMERVQXhMRmc5TUVBeUxGazlNemNiUURRc1YybGtkR2c5TXpJeU5rQTBMRWhsYVdkb2REMHhOVGsySkRoaE5XWmhZek5oTFdJMlpETXRORFZoTlMwNVlUSTVMVFJtTVdZek1EUTNaR0l4TkFWSmRHVnROUVpRWVhKbGJuUUVVbTl2ZEFkRmJHVnRaVzUwQmt4bGJtZDBhQWxWYm1sMFZtRnNkV1VJVlc1cGRGUjVjR1VFVTNSaGNoRkViMk5yYVc1blEyOXVkR0ZwYm1WeU1CQkViMk5yYVc1blEyOXVkR0ZwYm1WeUJVbDBaVzAyRVVSdlkydHBibWREYjI1MFlXbHVaWEl4QlVsMFpXMDNEVVJ2WTNWdFpXNTBSM0p2ZFhBPTwvVmlld0xheW91dD4NCjwvRG9jdW1lbnRNYW5hZ2VyU3RhdGU+\" />\r\n  <SchemaModules>\r\n    <SchemaModule Name=\"CloneObjectModule\" Version=\"22.2.4.0\" IsNewNode=\"True\" />\r\n    <SchemaModule Name=\"SchedulerModuleBase\" Version=\"22.2.4.0\" IsNewNode=\"True\" />\r\n    <SchemaModule Name=\"SchedulerWindowsFormsModule\" Version=\"22.2.4.0\" IsNewNode=\"True\" />\r\n    <SchemaModule Name=\"SystemModule\" Version=\"22.2.4.0\" IsNewNode=\"True\" />\r\n    <SchemaModule Name=\"SystemWindowsFormsModule\" Version=\"22.2.4.0\" IsNewNode=\"True\" />\r\n  </SchemaModules>\r\n  <Templates>\r\n    <Template Id=\"DevExpress.ExpressApp.Win.Templates.LookupControlTemplate\" IsNewNode=\"True\">\r\n      <FormStates IsNewNode=\"True\">\r\n        <FormState Id=\"Image_LookupListView\" Width=\"1210\" Height=\"354\" IsNewNode=\"True\" />\r\n        <FormState Id=\"MSession_LookupListView\" Width=\"1210\" Height=\"354\" IsNewNode=\"True\" />\r\n        <FormState Id=\"ParticlePickingJob_LookupListView\" Width=\"949\" Height=\"354\" IsNewNode=\"True\" />\r\n      </FormStates>\r\n    </Template>\r\n    <Template Id=\"DevExpress.ExpressApp.Win.Templates.Ribbon.DetailRibbonFormV2\" IsNewNode=\"True\">\r\n      <FormStates IsNewNode=\"True\">\r\n        <FormState Id=\"Image_DetailView\" IsNewNode=\"True\" />\r\n        <FormState Id=\"Image_ListView\" IsNewNode=\"True\" />\r\n        <FormState Id=\"MSession_DetailView\" IsNewNode=\"True\" />\r\n        <FormState Id=\"ParticlePickingJob_DetailView\" State=\"Normal\" X=\"783\" Y=\"991\" Width=\"800\" Height=\"604\" IsNewNode=\"True\" />\r\n        <FormState Id=\"ParticlePickingJobItem_DetailView\" State=\"Normal\" X=\"442\" Y=\"442\" Width=\"1010\" Height=\"817\" IsNewNode=\"True\" />\r\n        <FormState Id=\"Project_DetailView\" IsNewNode=\"True\" />\r\n        <FormState Id=\"Project_ListView\" IsNewNode=\"True\" />\r\n      </FormStates>\r\n    </Template>\r\n    <Template Id=\"DevExpress.ExpressApp.Win.Templates.Ribbon.LightStyleMainRibbonForm\" DockManagerSettings=\"77u/PFh0cmFTZXJpYWxpemVyIHZlcnNpb249IjEuMCIgYXBwbGljYXRpb249IkRvY2tNYW5hZ2VyIj4NCiAgPHByb3BlcnR5IG5hbWU9IiNMYXlvdXRWZXJzaW9uIiAvPg0KICA8cHJvcGVydHkgbmFtZT0iI0xheW91dFNjYWxlRmFjdG9yIj5AMSxXaWR0aD0xQDEsSGVpZ2h0PTE8L3Byb3BlcnR5Pg0KICA8cHJvcGVydHkgbmFtZT0iQWxsb3dHbHlwaFNraW5uaW5nIj5mYWxzZTwvcHJvcGVydHk+DQogIDxwcm9wZXJ0eSBuYW1lPSJTdHlsZSI+RGVmYXVsdDwvcHJvcGVydHk+DQogIDxwcm9wZXJ0eSBuYW1lPSJBdXRvSGlkZGVuUGFuZWxDYXB0aW9uU2hvd01vZGUiPlNob3dGb3JBbGxQYW5lbHM8L3Byb3BlcnR5Pg0KICA8cHJvcGVydHkgbmFtZT0iQXV0b0hpZGVDb250YWluZXJzIiBpc2tleT0idHJ1ZSIgdmFsdWU9IjAiIC8+DQogIDxwcm9wZXJ0eSBuYW1lPSJEb2NraW5nT3B0aW9ucyIgaXNudWxsPSJ0cnVlIiBpc2tleT0idHJ1ZSI+DQogICAgPHByb3BlcnR5IG5hbWU9IkF1dG9IaWRlUGFuZWxWZXJ0aWNhbFRleHRPcmllbnRhdGlvbiI+RGVmYXVsdDwvcHJvcGVydHk+DQogICAgPHByb3BlcnR5IG5hbWU9IlRhYmJlZFBhbmVsVmVydGljYWxUZXh0T3JpZW50YXRpb24iPkRlZmF1bHQ8L3Byb3BlcnR5Pg0KICAgIDxwcm9wZXJ0eSBuYW1lPSJDdXN0b21SZXNpemVab25lVGhpY2tuZXNzIj4wPC9wcm9wZXJ0eT4NCiAgICA8cHJvcGVydHkgbmFtZT0iQ3Vyc29yRmxvYXRDYW5jZWxlZCIgaXNudWxsPSJ0cnVlIiAvPg0KICAgIDxwcm9wZXJ0eSBuYW1lPSJIaWRlSW1tZWRpYXRlbHlPbkF1dG9IaWRlIj5mYWxzZTwvcHJvcGVydHk+DQogICAgPHByb3BlcnR5IG5hbWU9IkhpZGVQYW5lbHNJbW1lZGlhdGVseSI+TmV2ZXI8L3Byb3BlcnR5Pg0KICAgIDxwcm9wZXJ0eSBuYW1lPSJDbG9zZUFjdGl2ZVRhYk9ubHkiPnRydWU8L3Byb3BlcnR5Pg0KICAgIDxwcm9wZXJ0eSBuYW1lPSJDbG9zZUFjdGl2ZUZsb2F0VGFiT25seSI+ZmFsc2U8L3Byb3BlcnR5Pg0KICAgIDxwcm9wZXJ0eSBuYW1lPSJTaG93Q2FwdGlvbk9uTW91c2VIb3ZlciI+ZmFsc2U8L3Byb3BlcnR5Pg0KICAgIDxwcm9wZXJ0eSBuYW1lPSJTaG93Q2FwdGlvbkltYWdlIj5mYWxzZTwvcHJvcGVydHk+DQogICAgPHByb3BlcnR5IG5hbWU9IkZsb2F0UGFuZWxzQWx3YXlzT25Ub3AiPkRlZmF1bHQ8L3Byb3BlcnR5Pg0KICAgIDxwcm9wZXJ0eSBuYW1lPSJBbGxvd1Jlc3RvcmVUb0F1dG9IaWRlQ29udGFpbmVyIj5mYWxzZTwvcHJvcGVydHk+DQogICAgPHByb3BlcnR5IG5hbWU9IkFsbG93RG9ja1RvQ2VudGVyIj5EZWZhdWx0PC9wcm9wZXJ0eT4NCiAgICA8cHJvcGVydHkgbmFtZT0iRG9ja1BhbmVsSW5UYWJDb250YWluZXJUYWJSZWdpb24iPkRvY2tJbW1lZGlhdGVseTwvcHJvcGVydHk+DQogICAgPHByb3BlcnR5IG5hbWU9IkRvY2tQYW5lbEluQ2FwdGlvblJlZ2lvbiI+RGVmYXVsdDwvcHJvcGVydHk+DQogICAgPHByb3BlcnR5IG5hbWU9IlNuYXBNb2RlIj5Ob25lPC9wcm9wZXJ0eT4NCiAgICA8cHJvcGVydHkgbmFtZT0iU2hvd01heGltaXplQnV0dG9uIj50cnVlPC9wcm9wZXJ0eT4NCiAgICA8cHJvcGVydHkgbmFtZT0iU2hvd01pbmltaXplQnV0dG9uIj50cnVlPC9wcm9wZXJ0eT4NCiAgICA8cHJvcGVydHkgbmFtZT0iU2hvd0F1dG9IaWRlQnV0dG9uIj50cnVlPC9wcm9wZXJ0eT4NCiAgICA8cHJvcGVydHkgbmFtZT0iU2hvd0Nsb3NlQnV0dG9uIj50cnVlPC9wcm9wZXJ0eT4NCiAgICA8cHJvcGVydHkgbmFtZT0iRmxvYXRPbkRibENsaWNrIj50cnVlPC9wcm9wZXJ0eT4NCiAgPC9wcm9wZXJ0eT4NCiAgPHByb3BlcnR5IG5hbWU9IkFjdGl2ZVBhbmVsSUQiPi0xPC9wcm9wZXJ0eT4NCiAgPHByb3BlcnR5IG5hbWU9Ilh0cmFTZXJpYWxpemFibGVTY3JlZW5Db25maWd1cmF0aW9uIiBpc2tleT0idHJ1ZSIgdmFsdWU9IjEiPg0KICAgIDxwcm9wZXJ0eSBuYW1lPSJJdGVtMSI+QDEsWD0wQDEsWT0wQDQsV2lkdGg9MzQyNkA0LEhlaWdodD0xOTE5PC9wcm9wZXJ0eT4NCiAgPC9wcm9wZXJ0eT4NCiAgPHByb3BlcnR5IG5hbWU9IlBhbmVscyIgaXNrZXk9InRydWUiIHZhbHVlPSIwIiAvPg0KICA8cHJvcGVydHkgbmFtZT0iVG9wWkluZGV4Q29udHJvbHMiIGlza2V5PSJ0cnVlIiB2YWx1ZT0iMiI+DQogICAgPHByb3BlcnR5IG5hbWU9Ikl0ZW0xIiB0eXBlPSJTeXN0ZW0uU3RyaW5nIj5EZXZFeHByZXNzLkV4cHJlc3NBcHAuV2luLlRlbXBsYXRlcy5SaWJib24uWGFmUmliYm9uQ29udHJvbFYyPC9wcm9wZXJ0eT4NCiAgICA8cHJvcGVydHkgbmFtZT0iSXRlbTIiIHR5cGU9IlN5c3RlbS5TdHJpbmciPkRldkV4cHJlc3MuWHRyYUJhcnMuUmliYm9uLlJpYmJvblN0YXR1c0JhcjwvcHJvcGVydHk+DQogIDwvcHJvcGVydHk+DQo8L1h0cmFTZXJpYWxpemVyPg==\" IsNewNode=\"True\">\r\n      <FormStates IsNewNode=\"True\">\r\n        <FormState Id=\"Default\" State=\"Maximized\" MaximizedOnScreen=\"\\\\.\\DISPLAY1\" X=\"286\" Y=\"286\" Width=\"884\" Height=\"646\" IsNewNode=\"True\" />\r\n      </FormStates>\r\n      <NavBarCustomization Width=\"200\" IsNewNode=\"True\" />\r\n    </Template>\r\n  </Templates>\r\n  <Views>\r\n    <DetailView Id=\"ParticlePickingJobItem_DetailView\">\r\n      <Layout>\r\n        <LayoutGroup Id=\"Main\" RelativeSize=\"100\">\r\n          <LayoutGroup Id=\"SimpleEditors\" RelativeSize=\"19.031141868512112\">\r\n            <LayoutGroup Id=\"ParticlePickingJobItem\" RelativeSize=\"100\">\r\n              <LayoutItem Id=\"status\" RelativeSize=\"36.36363636363637\" />\r\n              <LayoutItem Id=\"job\" ViewItem=\"job\" Index=\"1\" RelativeSize=\"29.09090909090909\" IsNewNode=\"True\" />\r\n              <LayoutItem Id=\"type\" Index=\"2\" RelativeSize=\"34.54545454545455\" />\r\n            </LayoutGroup>\r\n          </LayoutGroup>\r\n          <LayoutGroup Id=\"SizeableEditors\" RelativeSize=\"80.96885813148789\" />\r\n        </LayoutGroup>\r\n      </Layout>\r\n    </DetailView>\r\n  </Views>\r\n</Application>','�O�@@��o�\"�G|',13,NULL);

/*Table structure for table `msession` */

DROP TABLE IF EXISTS `msession`;

CREATE TABLE `msession` (
  `Oid` binary(16) NOT NULL,
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
  PRIMARY KEY (`Oid`),
  KEY `iGCRecord_MSession` (`GCRecord`),
  KEY `iproject_MSession` (`project_id`),
  KEY `isite_MSession` (`site_id`),
  KEY `iuser_MSession` (`user_id`),
  KEY `imicroscope_MSession` (`microscope_id`),
  KEY `icamera_MSession` (`camera_id`),
  KEY `isample_type_MSession` (`sample_type`),
  KEY `isample_grid_type_MSession` (`sample_grid_type`),
  CONSTRAINT `FK_MSession_camera` FOREIGN KEY (`camera_id`) REFERENCES `camera` (`Oid`),
  CONSTRAINT `FK_MSession_microscope` FOREIGN KEY (`microscope_id`) REFERENCES `microscope` (`Oid`),
  CONSTRAINT `FK_MSession_project` FOREIGN KEY (`project_id`) REFERENCES `project` (`Oid`),
  CONSTRAINT `FK_MSession_sample_grid_type` FOREIGN KEY (`sample_grid_type`) REFERENCES `samplegridtype` (`Oid`),
  CONSTRAINT `FK_MSession_sample_type` FOREIGN KEY (`sample_type`) REFERENCES `sampletype` (`Oid`),
  CONSTRAINT `FK_MSession_site` FOREIGN KEY (`site_id`) REFERENCES `site` (`Oid`),
  CONSTRAINT `FK_MSession_user` FOREIGN KEY (`user_id`) REFERENCES `sys_sec_party` (`Oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

/*Data for the table `msession` */

insert  into `msession`(`Oid`,`name`,`project_id`,`site_id`,`user_id`,`description`,`start_on`,`end_on`,`microscope_id`,`camera_id`,`sample_type`,`sample_name`,`sample_grid_type`,`sample_sequence`,`sample_procedure`,`OptimisticLockField`,`GCRecord`) values 
('I�7MMG��-�/�','21aug26a','勳l��B��yхъ�',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL),
('`F�fJ܋�O�4N','22apr01a','勳l��B��yхъ�',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL),
('�+����A�0EsfZ','23jun14a','勳l��B��yхъ�',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL),
('�\0` sI�-��~�','23mar23b','勳l��B��yхъ�',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL),
('�@7�\nJ��i���B�','my session','̾�D��KK�P����',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'apofrin',NULL,'MVHLTPEEKSAVTALWGKVNVDEVGGEALGRLLVVYPWTQRFFESFGDLSTPDAVMGNPKVKAHGKKVLGAFSDGLAHLDNLKGTFATLSELHCDKLHVDPENFRLLGNVLVCVLAHHFGKEFTPPVQAAYQKVVAGVANALAHKYH\r\nRI',NULL,3,NULL);

/*Table structure for table `particlepickingjob` */

DROP TABLE IF EXISTS `particlepickingjob`;

CREATE TABLE `particlepickingjob` (
  `Oid` binary(16) NOT NULL,
  `name` varchar(100) DEFAULT NULL,
  `description` text DEFAULT NULL,
  `created_on` datetime DEFAULT NULL,
  `start_on` datetime DEFAULT NULL,
  `end_on` datetime DEFAULT NULL,
  `user_id` binary(16) DEFAULT NULL,
  `project_id` binary(16) DEFAULT NULL,
  `msession_id` binary(16) DEFAULT NULL,
  `status` int(11) DEFAULT NULL,
  `type` int(11) DEFAULT NULL,
  `settings` longtext DEFAULT NULL,
  `cs` decimal(28,8) DEFAULT NULL,
  `path` varchar(255) DEFAULT NULL,
  `output_dir` varchar(100) DEFAULT NULL,
  `direction` smallint(5) unsigned DEFAULT NULL,
  `image_selection_criteria` text DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  PRIMARY KEY (`Oid`),
  KEY `iGCRecord_ParticlePickingJob` (`GCRecord`),
  KEY `iuser_id_ParticlePickingJob` (`user_id`),
  KEY `iproject_id_ParticlePickingJob` (`project_id`),
  KEY `imsession_id_ParticlePickingJob` (`msession_id`),
  CONSTRAINT `FK_ParticlePickingJob_msession_id` FOREIGN KEY (`msession_id`) REFERENCES `msession` (`Oid`),
  CONSTRAINT `FK_ParticlePickingJob_project_id` FOREIGN KEY (`project_id`) REFERENCES `project` (`Oid`),
  CONSTRAINT `FK_ParticlePickingJob_user_id` FOREIGN KEY (`user_id`) REFERENCES `sys_sec_party` (`Oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

/*Data for the table `particlepickingjob` */

/*Table structure for table `particlepickingjobitem` */

DROP TABLE IF EXISTS `particlepickingjobitem`;

CREATE TABLE `particlepickingjobitem` (
  `Oid` binary(16) NOT NULL,
  `job_id` binary(16) DEFAULT NULL,
  `image_id` binary(16) DEFAULT NULL,
  `settings` longtext DEFAULT NULL,
  `status` int(11) DEFAULT NULL,
  `type` int(11) DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  `steps` int(11) DEFAULT NULL,
  PRIMARY KEY (`Oid`),
  KEY `iGCRecord_ParticlePickingJobItem` (`GCRecord`),
  KEY `ijob_id_ParticlePickingJobItem` (`job_id`),
  KEY `iimage_id_ParticlePickingJobItem` (`image_id`),
  CONSTRAINT `FK_ParticlePickingJobItem_image_id` FOREIGN KEY (`image_id`) REFERENCES `image` (`Oid`),
  CONSTRAINT `FK_ParticlePickingJobItem_job_id` FOREIGN KEY (`job_id`) REFERENCES `particlepickingjob` (`Oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

/*Data for the table `particlepickingjobitem` */

/*Table structure for table `project` */

DROP TABLE IF EXISTS `project`;

CREATE TABLE `project` (
  `Oid` binary(16) NOT NULL,
  `name` varchar(30) DEFAULT NULL,
  `description` varchar(200) DEFAULT NULL,
  `start_on` datetime DEFAULT NULL,
  `end_on` datetime DEFAULT NULL,
  `owner_id` binary(16) DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  PRIMARY KEY (`Oid`),
  KEY `iGCRecord_Project` (`GCRecord`),
  KEY `iowner_Project` (`owner_id`),
  CONSTRAINT `FK_Project_owner` FOREIGN KEY (`owner_id`) REFERENCES `sys_sec_party` (`Oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

/*Data for the table `project` */

insert  into `project`(`Oid`,`name`,`description`,`start_on`,`end_on`,`owner_id`,`OptimisticLockField`,`GCRecord`) values 
('̾�D��KK�P����','Apofrin project',NULL,NULL,NULL,NULL,1,NULL),
('勳l��B��yхъ�','Leginon',NULL,NULL,NULL,NULL,NULL,NULL);

/*Table structure for table `samplegridtype` */

DROP TABLE IF EXISTS `samplegridtype`;

CREATE TABLE `samplegridtype` (
  `Oid` binary(16) NOT NULL,
  `name` varchar(30) DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  PRIMARY KEY (`Oid`),
  KEY `iGCRecord_SampleGridType` (`GCRecord`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

/*Data for the table `samplegridtype` */

/*Table structure for table `samplematerial` */

DROP TABLE IF EXISTS `samplematerial`;

CREATE TABLE `samplematerial` (
  `Oid` binary(16) NOT NULL,
  `session` binary(16) DEFAULT NULL,
  `name` varchar(30) DEFAULT NULL,
  `quantity` decimal(28,8) DEFAULT NULL,
  `note` varchar(150) DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  PRIMARY KEY (`Oid`),
  KEY `iGCRecord_SampleMaterial` (`GCRecord`),
  KEY `isession_SampleMaterial` (`session`),
  CONSTRAINT `FK_SampleMaterial_session` FOREIGN KEY (`session`) REFERENCES `msession` (`Oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

/*Data for the table `samplematerial` */

/*Table structure for table `sampletype` */

DROP TABLE IF EXISTS `sampletype`;

CREATE TABLE `sampletype` (
  `Oid` binary(16) NOT NULL,
  `name` varchar(30) DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  PRIMARY KEY (`Oid`),
  KEY `iGCRecord_SampleType` (`GCRecord`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

/*Data for the table `sampletype` */

/*Table structure for table `site` */

DROP TABLE IF EXISTS `site`;

CREATE TABLE `site` (
  `Oid` binary(16) NOT NULL,
  `name` varchar(30) DEFAULT NULL,
  `address` varchar(150) DEFAULT NULL,
  `manager_id` binary(16) DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  PRIMARY KEY (`Oid`),
  KEY `iGCRecord_Site` (`GCRecord`),
  KEY `imanager_Site` (`manager_id`),
  CONSTRAINT `FK_Site_manager` FOREIGN KEY (`manager_id`) REFERENCES `sys_sec_party` (`Oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

/*Data for the table `site` */

/*Table structure for table `sys_sec_actionpermission` */

DROP TABLE IF EXISTS `sys_sec_actionpermission`;

CREATE TABLE `sys_sec_actionpermission` (
  `Oid` binary(16) NOT NULL,
  `ActionId` varchar(100) DEFAULT NULL,
  `Role` binary(16) DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  PRIMARY KEY (`Oid`),
  KEY `iGCRecord_sys_sec_actionpermission` (`GCRecord`),
  KEY `iRole_sys_sec_actionpermission` (`Role`),
  CONSTRAINT `FK_sys_sec_actionpermission_Role` FOREIGN KEY (`Role`) REFERENCES `sys_sec_role` (`Oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

/*Data for the table `sys_sec_actionpermission` */

/*Table structure for table `sys_sec_logininfo` */

DROP TABLE IF EXISTS `sys_sec_logininfo`;

CREATE TABLE `sys_sec_logininfo` (
  `Oid` binary(16) NOT NULL,
  `LoginProviderName` varchar(100) DEFAULT NULL,
  `ProviderUserKey` varchar(100) DEFAULT NULL,
  `User` binary(16) DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  PRIMARY KEY (`Oid`),
  UNIQUE KEY `iLoginProviderNameProviderUserKey_sys_sec_logininfo` (`LoginProviderName`,`ProviderUserKey`),
  KEY `iUser_sys_sec_logininfo` (`User`),
  CONSTRAINT `FK_sys_sec_logininfo_User` FOREIGN KEY (`User`) REFERENCES `sys_sec_party` (`Oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

/*Data for the table `sys_sec_logininfo` */

insert  into `sys_sec_logininfo`(`Oid`,`LoginProviderName`,`ProviderUserKey`,`User`,`OptimisticLockField`) values 
('X��/���C�	�f^ȁ','Password','ca1544d3-c664-4676-9bcd-c81aa9fead64','�D�d�vF���\Z���d',0),
('�@��G�jL��m��','Password','44204960-8096-4f54-bfc6-548b6ffb71db','`I D��TO��T�o�q�',0);

/*Table structure for table `sys_sec_memberpermission` */

DROP TABLE IF EXISTS `sys_sec_memberpermission`;

CREATE TABLE `sys_sec_memberpermission` (
  `Oid` binary(16) NOT NULL,
  `Members` longtext DEFAULT NULL,
  `ReadState` int(11) DEFAULT NULL,
  `WriteState` int(11) DEFAULT NULL,
  `Criteria` longtext DEFAULT NULL,
  `TypePermissionObject` binary(16) DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  PRIMARY KEY (`Oid`),
  KEY `iGCRecord_sys_sec_memberPermission` (`GCRecord`),
  KEY `iTypePermissionObject_sys_sec_memberPermission` (`TypePermissionObject`),
  CONSTRAINT `FK_sys_sec_memberPermission_TypePermissionObject` FOREIGN KEY (`TypePermissionObject`) REFERENCES `sys_sec_typepermission` (`Oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

/*Data for the table `sys_sec_memberpermission` */

insert  into `sys_sec_memberpermission`(`Oid`,`Members`,`ReadState`,`WriteState`,`Criteria`,`TypePermissionObject`,`OptimisticLockField`,`GCRecord`) values 
('��MjTrH��Q����','ChangePasswordOnFirstLogon',NULL,1,'[Oid] = CurrentUserId()','�?5�GG*E����˗',0,NULL),
('�`�����N�e\0��`','StoredPassword',NULL,1,'[Oid] = CurrentUserId()','�?5�GG*E����˗',0,NULL);

/*Table structure for table `sys_sec_navigationpermission` */

DROP TABLE IF EXISTS `sys_sec_navigationpermission`;

CREATE TABLE `sys_sec_navigationpermission` (
  `Oid` binary(16) NOT NULL,
  `ItemPath` longtext DEFAULT NULL,
  `NavigateState` int(11) DEFAULT NULL,
  `Role` binary(16) DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  PRIMARY KEY (`Oid`),
  KEY `iGCRecord_sys_sec_navigationpermission` (`GCRecord`),
  KEY `iRole_sys_sec_navigationpermission` (`Role`),
  CONSTRAINT `FK_sys_sec_navigationpermission_Role` FOREIGN KEY (`Role`) REFERENCES `sys_sec_role` (`Oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

/*Data for the table `sys_sec_navigationpermission` */

insert  into `sys_sec_navigationpermission`(`Oid`,`ItemPath`,`NavigateState`,`Role`,`OptimisticLockField`,`GCRecord`) values 
('�(Y�OM�*��U�%�','Application/NavigationItems/Items/Default/Items/MyDetails',1,'����yl@�<�7H�`y',0,NULL);

/*Table structure for table `sys_sec_objectpermission` */

DROP TABLE IF EXISTS `sys_sec_objectpermission`;

CREATE TABLE `sys_sec_objectpermission` (
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
  KEY `iGCRecord_sys_sec_objectPermission` (`GCRecord`),
  KEY `iTypePermissionObject_sys_sec_objectPermission` (`TypePermissionObject`),
  CONSTRAINT `FK_sys_sec_objectPermission_TypePermissionObject` FOREIGN KEY (`TypePermissionObject`) REFERENCES `sys_sec_typepermission` (`Oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

/*Data for the table `sys_sec_objectpermission` */

insert  into `sys_sec_objectpermission`(`Oid`,`Criteria`,`ReadState`,`WriteState`,`DeleteState`,`NavigateState`,`TypePermissionObject`,`OptimisticLockField`,`GCRecord`) values 
('ضT�Z�C�)q����','[Oid] = CurrentUserId()',1,NULL,NULL,NULL,'�?5�GG*E����˗',0,NULL);

/*Table structure for table `sys_sec_party` */

DROP TABLE IF EXISTS `sys_sec_party`;

CREATE TABLE `sys_sec_party` (
  `Oid` binary(16) NOT NULL,
  `omid` bigint(20) DEFAULT NULL,
  `ouid` varchar(20) DEFAULT NULL,
  `createdOn` datetime DEFAULT NULL,
  `createdBy` binary(16) DEFAULT NULL,
  `lastModifiedOn` datetime DEFAULT NULL,
  `lastModifiedBy` binary(16) DEFAULT NULL,
  `syncStatus` int(11) DEFAULT NULL,
  `version` bigint(20) DEFAULT NULL,
  `Color` int(11) DEFAULT NULL,
  `fullName` varchar(100) DEFAULT NULL,
  `mobile` varchar(15) DEFAULT NULL,
  `phone` varchar(15) DEFAULT NULL,
  `email` varchar(100) DEFAULT NULL,
  `address` varchar(100) DEFAULT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  `GCRecord` int(11) DEFAULT NULL,
  `ObjectType` int(11) DEFAULT NULL,
  `Password` longtext DEFAULT NULL,
  `ChangePasswordOnFirstLogon` bit(1) DEFAULT NULL,
  `UserName` varchar(100) DEFAULT NULL,
  `IsActive` bit(1) DEFAULT NULL,
  `photo` longblob DEFAULT NULL,
  PRIMARY KEY (`Oid`),
  KEY `iGCRecord_sys_sec_party` (`GCRecord`),
  KEY `icreatedBy_sys_sec_party` (`createdBy`),
  KEY `ilastModifiedBy_sys_sec_party` (`lastModifiedBy`),
  KEY `iObjectType_sys_sec_party` (`ObjectType`),
  CONSTRAINT `FK_sys_sec_party_ObjectType` FOREIGN KEY (`ObjectType`) REFERENCES `xpobjecttype` (`OID`),
  CONSTRAINT `FK_sys_sec_party_createdBy` FOREIGN KEY (`createdBy`) REFERENCES `sys_sec_party` (`Oid`),
  CONSTRAINT `FK_sys_sec_party_lastModifiedBy` FOREIGN KEY (`lastModifiedBy`) REFERENCES `sys_sec_party` (`Oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

/*Data for the table `sys_sec_party` */

insert  into `sys_sec_party`(`Oid`,`omid`,`ouid`,`createdOn`,`createdBy`,`lastModifiedOn`,`lastModifiedBy`,`syncStatus`,`version`,`Color`,`fullName`,`mobile`,`phone`,`email`,`address`,`OptimisticLockField`,`GCRecord`,`ObjectType`,`Password`,`ChangePasswordOnFirstLogon`,`UserName`,`IsActive`,`photo`) values 
('`I D��TO��T�o�q�',0,NULL,'2023-04-11 10:36:34',NULL,NULL,NULL,0,0,0,NULL,NULL,NULL,NULL,NULL,0,NULL,1,'$2a$11$UqoEXjoxz2mDY.IVyipdl.4qTcCiZM40tAYlBWfoBC/UNxe1G.Wxq','\0','Admin','',NULL),
('�D�d�vF���\Z���d',0,NULL,'2023-04-11 10:36:33',NULL,NULL,NULL,0,0,0,NULL,NULL,NULL,NULL,NULL,0,NULL,1,'$2a$11$slvef.2LaNj8z6pXZC/BfOlJqpFNhCPeV/o1ea7kghKyKhX4V5ULO','\0','User','',NULL);

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

/*Data for the table `sys_sec_role` */

insert  into `sys_sec_role`(`Oid`,`Name`,`IsAdministrative`,`CanEditModel`,`PermissionPolicy`,`OptimisticLockField`,`GCRecord`,`ObjectType`) values 
(')@�M�\0C�G��D�N','Administrators','','\0',0,0,NULL,2),
('����yl@�<�7H�`y','Default','\0','\0',0,0,NULL,2);

/*Table structure for table `sys_sec_typepermission` */

DROP TABLE IF EXISTS `sys_sec_typepermission`;

CREATE TABLE `sys_sec_typepermission` (
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
  KEY `iGCRecord_sys_sec_typePermission` (`GCRecord`),
  KEY `iRole_sys_sec_typePermission` (`Role`),
  CONSTRAINT `FK_sys_sec_typePermission_Role` FOREIGN KEY (`Role`) REFERENCES `sys_sec_role` (`Oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

/*Data for the table `sys_sec_typepermission` */

insert  into `sys_sec_typepermission`(`Oid`,`Role`,`TargetType`,`ReadState`,`WriteState`,`CreateState`,`DeleteState`,`NavigateState`,`OptimisticLockField`,`GCRecord`) values 
('a���H��cD{�Mu','����yl@�<�7H�`y','DevExpress.Persistent.BaseImpl.ModelDifference',1,1,1,NULL,NULL,0,NULL),
('d���<ؚF���d��','����yl@�<�7H�`y','org.magellon.security.PermissionPolicyRole',0,NULL,NULL,NULL,NULL,0,NULL),
('�?5�GG*E����˗','����yl@�<�7H�`y','org.magellon.security.User',NULL,NULL,NULL,NULL,NULL,0,NULL),
('�����\"�J�\n�>�Z','����yl@�<�7H�`y','DevExpress.Persistent.BaseImpl.ModelDifferenceAspect',1,1,1,NULL,NULL,0,NULL);

/*Table structure for table `sys_sec_userrole` */

DROP TABLE IF EXISTS `sys_sec_userrole`;

CREATE TABLE `sys_sec_userrole` (
  `People` binary(16) DEFAULT NULL,
  `Roles` binary(16) DEFAULT NULL,
  `OID` binary(16) NOT NULL,
  `OptimisticLockField` int(11) DEFAULT NULL,
  PRIMARY KEY (`OID`),
  UNIQUE KEY `iPeopleRoles_sys_sec_userrole` (`People`,`Roles`),
  KEY `iPeople_sys_sec_userrole` (`People`),
  KEY `iRoles_sys_sec_userrole` (`Roles`),
  CONSTRAINT `FK_sys_sec_userrole_People` FOREIGN KEY (`People`) REFERENCES `sys_sec_party` (`Oid`),
  CONSTRAINT `FK_sys_sec_userrole_Roles` FOREIGN KEY (`Roles`) REFERENCES `sys_sec_role` (`Oid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

/*Data for the table `sys_sec_userrole` */

insert  into `sys_sec_userrole`(`People`,`Roles`,`OID`,`OptimisticLockField`) values 
('`I D��TO��T�o�q�',')@�M�\0C�G��D�N','AI�n��6N�~u�;Q�',0),
('�D�d�vF���\Z���d','����yl@�<�7H�`y','�Pfh�G�PCB���',0);

/*Table structure for table `xpobjecttype` */

DROP TABLE IF EXISTS `xpobjecttype`;

CREATE TABLE `xpobjecttype` (
  `OID` int(11) NOT NULL AUTO_INCREMENT,
  `TypeName` varchar(254) DEFAULT NULL,
  `AssemblyName` varchar(254) DEFAULT NULL,
  PRIMARY KEY (`OID`),
  UNIQUE KEY `iTypeName_XPObjectType` (`TypeName`)
) ENGINE=InnoDB AUTO_INCREMENT=16 DEFAULT CHARSET=utf8 COLLATE=utf8_general_ci;

/*Data for the table `xpobjecttype` */

insert  into `xpobjecttype`(`OID`,`TypeName`,`AssemblyName`) values 
(1,'org.magellon.security.User','Magellon.Module'),
(2,'org.magellon.security.PermissionPolicyRole','Magellon.Module'),
(3,'org.magellon.security.ApplicationUserLoginInfo','Magellon.Module'),
(4,'org.magellon.security.PermissionPolicyTypePermissionObject','Magellon.Module'),
(5,'org.magellon.security.PermissionPolicyObjectPermissionsObject','Magellon.Module'),
(6,'org.magellon.security.PermissionPolicyNavigationPermissionObject','Magellon.Module'),
(7,'org.magellon.security.PermissionPolicyMemberPermissionsObject','Magellon.Module'),
(8,'sys_sec_userrole',''),
(9,'org.magellon.project.Project','Magellon.Module'),
(10,'org.magellon.project.MSession','Magellon.Module'),
(11,'org.magellon.project.Image','Magellon.Module'),
(12,'DevExpress.Persistent.BaseImpl.ModelDifference','DevExpress.Persistent.BaseImpl.Xpo.v22.2'),
(13,'DevExpress.Persistent.BaseImpl.ModelDifferenceAspect','DevExpress.Persistent.BaseImpl.Xpo.v22.2'),
(14,'org.magellon.project.ParticlePickingJobItem','Magellon.Module'),
(15,'org.magellon.project.ParticlePickingJob','Magellon.Module');

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
