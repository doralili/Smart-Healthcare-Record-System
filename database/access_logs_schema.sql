-- =====================================================
-- access_logs 表（审计日志表）
-- 用于记录所有关键访问行为，支持审计和防篡改验证
-- =====================================================

CREATE TABLE IF NOT EXISTS access_logs (
    id SERIAL PRIMARY KEY,
    doctor_id INTEGER NOT NULL,
    patient_id INTEGER NOT NULL,
    consent_id INTEGER,
    action VARCHAR(20) NOT NULL,
    record_scope VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 添加外键约束
ALTER TABLE access_logs ADD CONSTRAINT fk_access_logs_doctor 
    FOREIGN KEY (doctor_id) REFERENCES users(id) ON DELETE CASCADE;

ALTER TABLE access_logs ADD CONSTRAINT fk_access_logs_patient 
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE;

ALTER TABLE access_logs ADD CONSTRAINT fk_access_logs_consent 
    FOREIGN KEY (consent_id) REFERENCES consents(id) ON DELETE SET NULL;

-- 创建索引
CREATE INDEX idx_access_logs_doctor_id ON access_logs(doctor_id);
CREATE INDEX idx_access_logs_patient_id ON access_logs(patient_id);
CREATE INDEX idx_access_logs_action ON access_logs(action);
CREATE INDEX idx_access_logs_created_at ON access_logs(created_at);

-- 添加注释
COMMENT ON TABLE access_logs IS '审计日志表';
COMMENT ON COLUMN access_logs.action IS '操作类型: ACCESS(成功访问), DENIED(拒绝访问), APPROVE(批准申请), REJECT(拒绝申请), REVOKE(撤销授权)';
COMMENT ON COLUMN access_logs.record_scope IS '授权范围: DEFAULT, EXTRA';

-- =====================================================
-- 哈希链字段（成员 D 后续补充）
-- ALTER TABLE access_logs ADD COLUMN prev_hash VARCHAR(64);
-- ALTER TABLE access_logs ADD COLUMN current_hash VARCHAR(64);
-- =====================================================