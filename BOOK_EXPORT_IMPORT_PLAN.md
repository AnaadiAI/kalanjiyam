# Book Export/Import System for Kalanjiyam

## **COMPLEXITY ASSESSMENT: HIGH RISK** ⚠️

### **Why This Is Complex and Risky:**

1. **Complex Data Relationships**: Books involve multiple interconnected tables:
   - `Project` (book metadata)
   - `Page` (individual pages)
   - `Revision` (version history for each page)
   - `Translation` (translations for each revision)
   - `Board`, `Thread`, `Post` (discussion data)
   - `User` (creator and contributors)

2. **File System Dependencies**: 
   - Original PDFs stored in `UPLOAD_FOLDER/projects/{slug}/pdf/source.pdf`
   - Page images stored in `UPLOAD_FOLDER/projects/{slug}/pages/{page_number}.jpg`
   - OCR bounding box data in database

3. **User ID Mapping Issues**: 
   - All data references user IDs that won't exist in target system
   - Need complex user mapping logic

4. **Database Constraints**: 
   - Foreign key relationships must be maintained
   - Unique constraints (slugs, usernames)
   - Referential integrity

5. **Large Data Volumes**: 
   - Books can have hundreds of pages
   - Each page has multiple revisions
   - File sizes can be substantial

## **Implementation Plan**

### **Phase 1: Export System (Lower Risk)** ✅ COMPLETED

**Files Created:**
- `kalanjiyam/views/admin/export.py` - Export functionality
- `kalanjiyam/views/admin/import.py` - Import functionality  
- `kalanjiyam/views/admin/__init__.py` - Admin views package
- `kalanjiyam/templates/admin/export_import.html` - Main interface
- `kalanjiyam/templates/admin/import.html` - Single project import
- `kalanjiyam/templates/admin/import_all.html` - All projects import

**Features Implemented:**
- ✅ Export single project with all data
- ✅ Export all projects in one ZIP
- ✅ Import single project from ZIP
- ✅ Import all projects from ZIP
- ✅ Admin-only access control
- ✅ User creation for missing authors
- ✅ File system handling (PDFs, images)
- ✅ Error handling and rollback
- ✅ Progress feedback

**URLs:**
- `/admin/` - Main export/import interface
- `/admin/export/project/<slug>` - Export single project
- `/admin/export/all-projects` - Export all projects
- `/admin/import` - Import single project
- `/admin/import/all-projects` - Import all projects

### **Phase 2: Testing and Validation (Critical)**

**Required Testing:**
1. **Unit Tests**: Test export/import functions
2. **Integration Tests**: Test with real data
3. **File System Tests**: Test file copying
4. **User Mapping Tests**: Test user creation
5. **Error Handling Tests**: Test rollback scenarios

**Validation Steps:**
1. Export a project from System A
2. Import to System B
3. Verify all data integrity
4. Test user access and permissions
5. Verify file accessibility

### **Phase 3: Production Deployment (High Risk)**

**Pre-deployment Checklist:**
- [ ] Database backup procedures in place
- [ ] File system backup procedures in place
- [ ] Admin user training completed
- [ ] Rollback procedures documented
- [ ] Monitoring and logging implemented
- [ ] Rate limiting for large imports
- [ ] File size limits configured

## **Usage Instructions**

### **For Admins:**

1. **Access the Interface:**
   ```
   https://your-kalanjiyam-instance/admin/
   ```

2. **Export a Single Project:**
   - Select project from dropdown
   - Click "Export"
   - Download ZIP file

3. **Export All Projects:**
   - Click "Export All Projects"
   - Wait for download (may take time)

4. **Import a Project:**
   - Click "Choose File" and select ZIP
   - Click "Import Project"
   - Wait for completion

5. **Import All Projects:**
   - Click "Choose File" and select ZIP
   - Click "Import All Projects"
   - Wait for completion (may take time)

### **For System Administrators:**

1. **Backup Before Import:**
   ```bash
   # Database backup
   pg_dump -h localhost -U kalanjiyam -d kalanjiyam > backup_before_import.sql
   
   # File system backup
   tar -czf file_backup_before_import.tar.gz /path/to/upload/folder
   ```

2. **Monitor Import Process:**
   - Check application logs
   - Monitor database size
   - Monitor disk space

3. **Post-import Tasks:**
   - Change placeholder user passwords
   - Verify data integrity
   - Test user access

## **Risk Mitigation Strategies**

### **1. Data Loss Prevention**
- **Database backups** before any import
- **File system backups** before any import
- **Transaction rollback** on import failure
- **Validation checks** before import

### **2. User Management**
- **Placeholder users** created with obvious passwords
- **Email notifications** to admins about new users
- **Password change requirements** for imported users
- **User mapping documentation**

### **3. Performance Management**
- **File size limits** on uploads
- **Progress indicators** for long operations
- **Background processing** for large imports
- **Memory management** for large files

### **4. Security Considerations**
- **Admin-only access** to import/export
- **File type validation** (ZIP only)
- **Path traversal protection**
- **Input sanitization**

## **Known Limitations**

1. **User Passwords**: Imported users get placeholder passwords
2. **File Permissions**: May need manual adjustment after import
3. **Large Files**: Very large projects may timeout
4. **Concurrent Imports**: Not recommended
5. **Cross-Version Compatibility**: May not work between different Kalanjiyam versions

## **Future Enhancements**

1. **User Mapping Interface**: Allow admins to map users before import
2. **Selective Import**: Choose which parts of a project to import
3. **Incremental Import**: Only import changes since last export
4. **Background Processing**: Use Celery for large imports
5. **Progress Tracking**: Real-time progress updates
6. **Validation Reports**: Detailed reports of what was imported
7. **Rollback Interface**: Easy way to undo imports

## **Emergency Procedures**

### **If Import Fails:**
1. Check application logs
2. Rollback database if needed
3. Clean up any partial files
4. Restore from backup if necessary

### **If Data Corruption Occurs:**
1. Stop all operations immediately
2. Restore from latest backup
3. Investigate root cause
4. Document incident

### **If Users Can't Access Imported Content:**
1. Check file permissions
2. Verify user roles and permissions
3. Check database constraints
4. Review import logs

## **Conclusion**

This export/import system provides a comprehensive solution for transferring books between Kalanjiyam instances. However, it is a **high-risk operation** that requires careful planning, testing, and monitoring. 

**Recommendations:**
1. Test thoroughly in development environment
2. Start with small projects
3. Always backup before importing
4. Monitor the process closely
5. Have rollback procedures ready
6. Train administrators on proper usage

The system is designed to be safe and reliable, but the complexity of the data relationships and file dependencies makes it inherently risky. Use with caution and always maintain proper backups.
