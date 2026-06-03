-- =====================================================
-- consents 表（授权记录表）
-- 用于存储医生与患者之间的授权关系
-- =====================================================

CREATE TABLE IF NOT EXISTS consents (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL,
    doctor_id INTEGER NOT NULL,
    record_scope VARCHAR(20) NOT NULL,
    permission VARCHAR(50),
    status VARCHAR(20) DEFAULT 'PENDING',
    request_reason TEXT,
    approve_note TEXT,
    consent_source VARCHAR(30) NOT NULL,
    default_scope VARCHAR(20),
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    auto_granted_at TIMESTAMP,
    approved_at TIMESTAMP,
    revoked_at TIMESTAMP
);

-- 添加外键约束（如果 users 和 patients 表已存在）
ALTER TABLE consents ADD CONSTRAINT fk_consents_patient 
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE;

ALTER TABLE consents ADD CONSTRAINT fk_consents_doctor 
    FOREIGN KEY (doctor_id) REFERENCES users(id) ON DELETE CASCADE;

-- 创建索引提高查询性能
CREATE INDEX idx_consents_patient_id ON consents(patient_id);
CREATE INDEX idx_consents_doctor_id ON consents(doctor_id);
CREATE INDEX idx_consents_status ON consents(status);

-- 防止同一医生对同一患者有多个 ACTIVE 授权
CREATE UNIQUE INDEX idx_unique_active_consent 
    ON consents (doctor_id, patient_id) 
    WHERE status = 'ACTIVE';

-- 防止同一医生对同一患者有多个 PENDING 申请
CREATE UNIQUE INDEX idx_unique_pending_consent 
    ON consents (doctor_id, patient_id) 
    WHERE status = 'PENDING';

-- 添加注释
COMMENT ON TABLE consents IS '医生-患者授权记录表';
COMMENT ON COLUMN consents.status IS '授权状态: ACTIVE(已授权), PENDING(待审批), REJECTED(已拒绝), REVOKED(已撤销)';
COMMENT ON COLUMN consents.record_scope IS '授权范围: DEFAULT(默认权限), EXTRA(完整权限)';
COMMENT ON COLUMN consents.consent_source IS '授权来源: SYSTEM(系统自动), EXPLICIT_REQUEST(医生申请)';