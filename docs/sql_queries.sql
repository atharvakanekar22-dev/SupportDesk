-- =============================================================================
-- SupportDesk — Verified SQL Report Queries for PostgreSQL
-- Tested and verified against active PostgreSQL schema (Django 5.1.4 / Python 3.14)
-- Database tables: tickets_ticket, accounts_user
-- =============================================================================

-- Query 1: Count tickets grouped by status
-- Purpose: Identifies the distribution of tickets across the lifecycle stages.
SELECT 
    status, 
    COUNT(*) AS ticket_count
FROM tickets_ticket
GROUP BY status
ORDER BY ticket_count DESC;


-- Query 2: Count tickets grouped by priority
-- Purpose: Identifies workload urgency across critical, high, medium, and low tiers.
SELECT 
    priority, 
    COUNT(*) AS ticket_count
FROM tickets_ticket
GROUP BY priority
ORDER BY ticket_count DESC;


-- Query 3: Count tickets grouped by assigned support agent
-- Purpose: Analyzes active workload distribution across all support engineers.
SELECT 
    u.id AS agent_id,
    u.username AS agent_username,
    COALESCE(TRIM(u.first_name || ' ' || u.last_name), u.username) AS agent_name,
    COUNT(t.id) AS ticket_count
FROM accounts_user u
LEFT JOIN tickets_ticket t ON u.id = t.assigned_agent_id
WHERE u.role = 'AGENT'
GROUP BY u.id, u.username, u.first_name, u.last_name
ORDER BY ticket_count DESC;
