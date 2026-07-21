# UK Compliance Platform — Disaster Recovery & Backup Plan

This document details the policies and processes for disaster recovery, database snapshots, and system restore.

## 1. Backup Schedule & Policies
1. **Daily Databases Snapshot:** Automatic full database backup executed daily at 02:00 UTC via Celery beat scheduler.
2. **File Storage Backups:** Automated backups of the uploaded files/documents directory compressed to zip archives.
3. **Retention Duration:** 30 days retention history. Archives older than 30 days are automatically purged.
4. **Storage Location:** Local persistent volume mounts, which are backed up to off-site secure object storage (AWS S3 or Azure Blob) in cloud environments.

---

## 2. Integrity Verification & Checksums
Every generated backup file creates a metadata file containing:
- **`sha256`:** SHA-256 hash checksum generated at completion time.
- **`files_count` & `size`:** File stats verification parameters.

On verification requests (triggered manually via DevOps Admin Panel or scheduled script):
1. The backup service calculates the file's current SHA-256 checksum.
2. Compares it with the recorded checksum.
3. Audit log registers `BACKUP_VERIFICATION_SUCCESS` or `BACKUP_VERIFICATION_FAILED`.

---

## 3. Database Restore Procedures
To restore the platform in the event of primary database corruption:

1. **Pause active API services:**
   ```bash
   kubectl scale deployment/aml-backend-api -n aml-compliance --replicas=0
   ```
2. **Access primary database pod:**
   ```bash
   kubectl exec -it statefulset/aml-postgres-primary -n aml-compliance -- /bin/bash
   ```
3. **Restore PostgreSQL dump:**
   ```bash
   pg_restore -U compliance_admin -d aml_compliance_db /backups/db_backup_2026-07-21.dump
   ```
4. **Verify database tables:**
   ```bash
   python check_tables.py
   ```
5. **Scale API services back up:**
   ```bash
   kubectl scale deployment/aml-backend-api -n aml-compliance --replicas=2
   ```

---

## 4. Database Replica Failover Strategy
If the primary PostgreSQL database goes offline:
1. Promote the read-replica database to primary:
   ```bash
   # Run on replica instance:
   pg_ctl promote -D /var/lib/postgresql/data
   ```
2. Update ConfigMaps (`DATABASE_URL`) to point to the promoted service instance address.
3. Trigger a rolling restart of the API deployment:
   ```bash
   kubectl rollout restart deployment/aml-backend-api -n aml-compliance
   ```
4. Confirm health via `/health/ready` endpoint.
