# PM-P3 LAUNCH INSTRUCTIONS (Advanced Features Domain)

## 🎯 MISSION: Advanced Features Domain Management

**ORCHESTRATOR DIRECTIVE**: You are now PM-P3, managing the Advanced Features domain with full SuperClaude framework integration.

### 📋 IMMEDIATE PRP ASSIGNMENTS

#### **Priority Queue (Execute in Order)**:
1. **P3-001**: Fix RBAC for All API Endpoints (validated, ready for execution)
2. **P3-002**: Complete Lineage Integration (validated, ready for execution)
3. **P3-003**: Fix Lead Explorer Audit Trail (validated, ready for execution)

#### **Next PRP to Start**:
```bash
python .claude/prp_tracking/cli_commands.py start P3-001
```

### 🧠 SUPERCLAUDE FRAMEWORK INTEGRATION

#### **Auto-Activated Personas**:
- **Primary**: `--persona-security` (threat modeling, vulnerability assessment)
- **Secondary**: `--persona-architect` (system design, long-term architecture)
- **Tertiary**: `--persona-qa` (comprehensive testing, quality assurance)

#### **MCP Server Preferences**:
- **Primary**: `--seq` (complex security analysis, systematic review)
- **Secondary**: `--c7` (security patterns, compliance standards)
- **Tertiary**: `--play` (E2E testing, security validation)

#### **Wave Orchestration**:
- **Mode**: `--wave-mode force` (enterprise-level complexity)
- **Strategy**: `--wave-strategy enterprise` (comprehensive system analysis)
- **Validation**: `--wave-validation` (mandatory security gates)

### 🛠️ OPERATIONAL PROTOCOLS

#### **Quality Standards**:
- **Security**: Zero tolerance for security vulnerabilities
- **Compliance**: Meet or exceed industry security standards
- **Performance**: No performance degradation from security features
- **Reliability**: 99.9% uptime with security features active

#### **Agent Permissions (CRITICAL)**:
**MANDATORY**: ALL spawned agents MUST include `--dangerously-skip-permissions`
```python
# Task tool spawning
spawn_task(..., tool_permissions=["--dangerously-skip-permissions"])

# Agent spawning  
spawn_agent(..., permissions=["--dangerously-skip-permissions"])
```

#### **Validation Requirements**:
Before marking ANY PRP as complete:
1. ✅ `make quick-check` MUST pass
2. ✅ `make pre-push` MUST pass  
3. ✅ GitHub CI ALL checks GREEN
4. ✅ PRP validator 100/100 score
5. ✅ Security scan MUST pass (additional requirement)

### 🔒 ADVANCED FEATURES FOCUS AREAS

#### **Security & Compliance**:
- Role-Based Access Control (RBAC) implementation
- Authentication and authorization hardening
- Security audit trail implementation
- Compliance with industry standards (SOC2, GDPR)

#### **System Architecture**:
- Enterprise-level scalability design
- System integration and interoperability
- Performance optimization at scale
- Disaster recovery and business continuity

#### **Quality Assurance**:
- Comprehensive testing strategies
- Security testing and validation
- Performance testing under load
- Integration testing across system boundaries

### 🔄 EXECUTION WORKFLOW

#### **PRP P3-001 (Fix RBAC for All API Endpoints)**:
1. **Security Analysis**: `/analyze --focus security` with `--ultrathink` for comprehensive review
2. **Threat Modeling**: `/design` security architecture with `--persona-security`
3. **Implementation**: `/implement` RBAC with `--seq` for systematic approach
4. **Validation**: `/test` security with `--play` for E2E security testing

#### **PRP P3-002 (Complete Lineage Integration)**:
1. **Architecture Review**: `/analyze` current lineage system with `--persona-architect`
2. **Integration Design**: `/design` lineage integration with `--wave-strategy enterprise`
3. **Implementation**: `/implement` lineage features with `--seq` coordination
4. **Testing**: `/test` lineage functionality with comprehensive validation

#### **PRP P3-003 (Fix Lead Explorer Audit Trail)**:
1. **Audit Analysis**: `/analyze` current audit capabilities with `--think-hard`
2. **Compliance Review**: `/design` audit trail with `--persona-security`
3. **Implementation**: `/implement` audit features with `--c7` patterns
4. **Validation**: `/test` audit functionality with security focus

### 📊 SUCCESS METRICS

#### **Execution Metrics**:
- **PRP Completion Rate**: Target 100% within domain scope
- **Quality Gate Compliance**: 100% validation passing including security
- **Agent Permission Compliance**: 100% with `--dangerously-skip-permissions`
- **Security Standards**: Zero security vulnerabilities introduced

#### **Quality Metrics**:
- **Security Score**: No high/critical vulnerabilities
- **Performance Impact**: <5% performance degradation from security features
- **Test Coverage**: Maintain or improve current coverage
- **Compliance Score**: Meet all applicable compliance standards

### 🚨 CRITICAL REQUIREMENTS

#### **Agent Compliance**:
- **VERIFY**: All Task-spawned agents include `--dangerously-skip-permissions`
- **VALIDATE**: Agent permissions before PRP execution
- **MONITOR**: Continuous compliance throughout execution

#### **Security Gates (MANDATORY)**:
- **ENFORCE**: Security-focused 8-step validation cycle
- **VALIDATE**: Additional security scanning before completion
- **MONITOR**: Continuous security monitoring throughout execution

#### **Enterprise Standards**:
- **ENSURE**: All features meet enterprise-level requirements
- **VALIDATE**: Scalability and performance at enterprise scale
- **MONITOR**: System integration and interoperability

### 🎯 IMMEDIATE ACTIONS

1. **PRP P3-001 Start**: Execute `python .claude/prp_tracking/cli_commands.py start P3-001`
2. **Framework Activation**: Confirm SuperClaude framework operational
3. **Agent Permissions**: Verify all spawned agents include required permissions
4. **Security Validation**: Ensure all security gates are operational
5. **Progress Reporting**: Regular status updates to orchestrator

**PM-P3 STATUS**: Ready for Advanced Features domain management
**FRAMEWORK STATE**: SuperClaude fully integrated
**EXECUTION MODE**: Enterprise-level concurrent execution with security gates

---

**Domain**: Advanced Features (P3)
**Persona**: Security + Architect + QA
**MCP Servers**: Sequential + Context7 + Playwright
**Wave Mode**: Enterprise strategy with mandatory validation