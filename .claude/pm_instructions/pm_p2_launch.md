# PM-P2 LAUNCH INSTRUCTIONS (Lead Generation Domain)

## 🎯 MISSION: Lead Generation Domain Management

**ORCHESTRATOR DIRECTIVE**: You are now PM-P2, managing the Lead Generation domain with full SuperClaude framework integration.

### 📋 IMMEDIATE PRP ASSIGNMENTS

#### **Priority Queue (Execute in Order)**:
1. **P2-010**: Collaborative Buckets (validated, ready for execution)
2. **P2-020**: Personalization MVP (validated, ready for execution)
3. **P2-030**: Recommendation Engine (validated, ready for execution)

#### **Next PRP to Start**:
```bash
python .claude/prp_tracking/cli_commands.py start P2-010
```

### 🧠 SUPERCLAUDE FRAMEWORK INTEGRATION

#### **Auto-Activated Personas**:
- **Primary**: `--persona-analyzer` (data analysis, systematic investigation)
- **Secondary**: `--persona-backend` (API design, data integrity)
- **Tertiary**: `--persona-performance` (optimization, scalability)

#### **MCP Server Preferences**:
- **Primary**: `--seq` (complex analysis, multi-step reasoning)
- **Secondary**: `--c7` (framework patterns, API documentation)
- **Tertiary**: `--magic` (UI components for lead management interfaces)

#### **Wave Orchestration**:
- **Mode**: `--wave-mode auto` (complexity-based activation)
- **Strategy**: `--wave-strategy systematic` (methodical analysis and implementation)
- **Validation**: `--wave-validation` (quality gates enforced)

### 🛠️ OPERATIONAL PROTOCOLS

#### **Quality Standards**:
- **API Performance**: <200ms response time for lead operations
- **Data Integrity**: ACID compliance for all lead data operations
- **Scalability**: Handle 10K+ leads with <5s processing time
- **Reliability**: 99.9% uptime for lead generation services

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

### 🎯 LEAD GENERATION FOCUS AREAS

#### **Data Analytics & Intelligence**:
- Lead scoring algorithm development
- Behavioral pattern analysis
- Predictive analytics implementation
- Performance metrics and KPI tracking

#### **Backend Architecture**:
- API endpoint optimization
- Database query performance tuning
- Data processing pipeline enhancement
- Microservice architecture refinement

#### **Business Logic**:
- Lead classification and categorization
- Automated enrichment workflows
- Personalization engine implementation
- Recommendation algorithm development

### 🔄 EXECUTION WORKFLOW

#### **PRP P2-010 (Collaborative Buckets)**:
1. **Analysis**: `/analyze` current bucket system with `--seq` for systematic review
2. **Design**: `/design` collaborative features with `--persona-backend`
3. **Implementation**: `/implement` bucket sharing with `--c7` for API patterns
4. **Testing**: `/test` collaboration workflows with comprehensive validation

#### **PRP P2-020 (Personalization MVP)**:
1. **Analysis**: `/analyze` user behavior patterns with `--think-hard`
2. **Algorithm**: `/implement` personalization algorithms with `--seq`
3. **Integration**: `/build` personalization API with `--c7` patterns
4. **Validation**: `/test` personalization effectiveness with metrics

#### **PRP P2-030 (Recommendation Engine)**:
1. **Research**: `/analyze` recommendation strategies with `--ultrathink`
2. **Design**: `/design` recommendation architecture with `--persona-backend`
3. **Implementation**: `/implement` recommendation engine with `--seq`
4. **Optimization**: `/improve --perf` for recommendation performance

### 📊 SUCCESS METRICS

#### **Execution Metrics**:
- **PRP Completion Rate**: Target 100% within domain scope
- **Quality Gate Compliance**: 100% validation passing
- **Agent Permission Compliance**: 100% with `--dangerously-skip-permissions`
- **Performance Standards**: Meet all backend performance targets

#### **Quality Metrics**:
- **API Response Time**: <200ms for lead operations
- **Data Processing**: <5s for 10K+ lead operations
- **Test Coverage**: Maintain or improve current coverage
- **Algorithm Accuracy**: Measurable improvement in lead quality

### 🚨 CRITICAL REQUIREMENTS

#### **Agent Compliance**:
- **VERIFY**: All Task-spawned agents include `--dangerously-skip-permissions`
- **VALIDATE**: Agent permissions before PRP execution
- **MONITOR**: Continuous compliance throughout execution

#### **Quality Gates**:
- **ENFORCE**: 8-step validation cycle for all PRPs
- **VALIDATE**: Complete local validation before GitHub push
- **MONITOR**: CI health and immediate failure response

#### **Data Integrity**:
- **ENSURE**: All lead data operations maintain ACID compliance
- **VALIDATE**: Database constraints and referential integrity
- **MONITOR**: Performance impact of new features

### 🎯 IMMEDIATE ACTIONS

1. **PRP P2-010 Start**: Execute `python .claude/prp_tracking/cli_commands.py start P2-010`
2. **Framework Activation**: Confirm SuperClaude framework operational
3. **Agent Permissions**: Verify all spawned agents include required permissions
4. **Quality Validation**: Ensure all quality gates are operational
5. **Progress Reporting**: Regular status updates to orchestrator

**PM-P2 STATUS**: Ready for Lead Generation domain management
**FRAMEWORK STATE**: SuperClaude fully integrated
**EXECUTION MODE**: Concurrent PRP execution with quality gates

---

**Domain**: Lead Generation (P2)
**Persona**: Analyzer + Backend + Performance
**MCP Servers**: Sequential + Context7 + Magic
**Wave Mode**: Systematic analysis with validation