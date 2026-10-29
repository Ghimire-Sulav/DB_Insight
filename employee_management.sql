-- Employee management system schema and sample data.
-- Run this script once against an empty database. IDs are explicit so the
-- script does not depend on a database-specific auto-increment feature.

CREATE TABLE Department (
    department_id   INTEGER       NOT NULL,
    department_name VARCHAR(100)  NOT NULL,
    location        VARCHAR(100)  NOT NULL,
    annual_budget   DECIMAL(14, 2) NOT NULL,
    CONSTRAINT pk_department PRIMARY KEY (department_id),
    CONSTRAINT uq_department_name UNIQUE (department_name),
    CONSTRAINT ck_department_budget CHECK (annual_budget >= 0)
);

CREATE TABLE Employee (
    employee_id   INTEGER       NOT NULL,
    department_id INTEGER       NOT NULL,
    first_name    VARCHAR(60)   NOT NULL,
    last_name     VARCHAR(60)   NOT NULL,
    email         VARCHAR(254)  NOT NULL,
    phone         VARCHAR(30),
    job_title     VARCHAR(100)  NOT NULL,
    hire_date     DATE          NOT NULL,
    salary        DECIMAL(12, 2) NOT NULL,
    CONSTRAINT pk_employee PRIMARY KEY (employee_id),
    CONSTRAINT uq_employee_email UNIQUE (email),
    CONSTRAINT ck_employee_salary CHECK (salary >= 0),
    CONSTRAINT fk_employee_department
        FOREIGN KEY (department_id) REFERENCES Department (department_id)
);

CREATE TABLE Project (
    project_id   INTEGER       NOT NULL,
    project_name VARCHAR(150)  NOT NULL,
    description  VARCHAR(500),
    start_date   DATE          NOT NULL,
    end_date     DATE,
    status       VARCHAR(20)   NOT NULL,
    budget       DECIMAL(14, 2) NOT NULL,
    CONSTRAINT pk_project PRIMARY KEY (project_id),
    CONSTRAINT uq_project_name UNIQUE (project_name),
    CONSTRAINT ck_project_dates CHECK (end_date IS NULL OR end_date >= start_date),
    CONSTRAINT ck_project_status
        CHECK (status IN ('Planned', 'Active', 'On Hold', 'Completed')),
    CONSTRAINT ck_project_budget CHECK (budget >= 0)
);

CREATE TABLE Employee_Project (
    employee_id   INTEGER       NOT NULL,
    project_id    INTEGER       NOT NULL,
    project_role  VARCHAR(100)  NOT NULL,
    assigned_date DATE          NOT NULL,
    hours_per_week DECIMAL(5, 2) NOT NULL,
    CONSTRAINT pk_employee_project PRIMARY KEY (employee_id, project_id),
    CONSTRAINT ck_employee_project_hours
        CHECK (hours_per_week > 0 AND hours_per_week <= 168),
    CONSTRAINT fk_employee_project_employee
        FOREIGN KEY (employee_id) REFERENCES Employee (employee_id),
    CONSTRAINT fk_employee_project_project
        FOREIGN KEY (project_id) REFERENCES Project (project_id)
);

INSERT INTO Department (department_id, department_name, location, annual_budget) VALUES
    (1, 'Engineering', 'Building A', 1800000.00),
    (2, 'Human Resources', 'Building B', 650000.00),
    (3, 'Finance', 'Building B', 900000.00),
    (4, 'Marketing', 'Building C', 1100000.00),
    (5, 'Operations', 'Building A', 1250000.00);

INSERT INTO Employee
    (employee_id, department_id, first_name, last_name, email, phone, job_title, hire_date, salary)
VALUES
    (1001, 1, 'Aarav', 'Sharma', 'aarav.sharma@example.com', '555-0101', 'Software Engineer', '2021-03-15', 92000.00),
    (1002, 1, 'Maya', 'Patel', 'maya.patel@example.com', '555-0102', 'Senior Software Engineer', '2019-07-08', 118000.00),
    (1003, 1, 'Noah', 'Kim', 'noah.kim@example.com', '555-0103', 'Database Engineer', '2022-01-10', 98000.00),
    (1004, 1, 'Sofia', 'Garcia', 'sofia.garcia@example.com', '555-0104', 'QA Engineer', '2020-11-02', 87000.00),
    (1005, 2, 'Liam', 'Wilson', 'liam.wilson@example.com', '555-0105', 'HR Manager', '2018-05-21', 105000.00),
    (1006, 2, 'Aisha', 'Khan', 'aisha.khan@example.com', '555-0106', 'HR Generalist', '2021-09-13', 72000.00),
    (1007, 2, 'Ethan', 'Brown', 'ethan.brown@example.com', '555-0107', 'Recruiter', '2023-02-06', 68000.00),
    (1008, 2, 'Priya', 'Singh', 'priya.singh@example.com', '555-0108', 'Learning Specialist', '2022-06-20', 74000.00),
    (1009, 3, 'Oliver', 'Martin', 'oliver.martin@example.com', '555-0109', 'Finance Manager', '2017-10-16', 122000.00),
    (1010, 3, 'Amara', 'Johnson', 'amara.johnson@example.com', '555-0110', 'Financial Analyst', '2020-04-27', 83000.00),
    (1011, 3, 'Lucas', 'Chen', 'lucas.chen@example.com', '555-0111', 'Accountant', '2022-08-01', 76000.00),
    (1012, 3, 'Zara', 'Ahmed', 'zara.ahmed@example.com', '555-0112', 'Payroll Specialist', '2021-12-06', 71000.00),
    (1013, 4, 'James', 'Taylor', 'james.taylor@example.com', '555-0113', 'Marketing Manager', '2019-02-18', 112000.00),
    (1014, 4, 'Isabella', 'Lopez', 'isabella.lopez@example.com', '555-0114', 'Content Strategist', '2022-03-14', 79000.00),
    (1015, 4, 'Benjamin', 'Davis', 'benjamin.davis@example.com', '555-0115', 'Digital Marketing Analyst', '2021-06-07', 81000.00),
    (1016, 4, 'Mei', 'Wong', 'mei.wong@example.com', '555-0116', 'Brand Designer', '2023-01-23', 77000.00),
    (1017, 5, 'Elijah', 'Thomas', 'elijah.thomas@example.com', '555-0117', 'Operations Manager', '2018-09-04', 115000.00),
    (1018, 5, 'Nina', 'Wilson', 'nina.wilson@example.com', '555-0118', 'Business Analyst', '2020-12-14', 88000.00),
    (1019, 5, 'Mateo', 'Rivera', 'mateo.rivera@example.com', '555-0119', 'Logistics Coordinator', '2022-05-09', 73000.00),
    (1020, 5, 'Chloe', 'Anderson', 'chloe.anderson@example.com', '555-0120', 'Process Improvement Analyst', '2021-10-25', 85000.00);

INSERT INTO Project
    (project_id, project_name, description, start_date, end_date, status, budget)
VALUES
    (2001, 'Customer Portal', 'Build a self-service customer portal.', '2025-01-15', NULL, 'Active', 450000.00),
    (2002, 'Data Warehouse', 'Centralize reporting data for the business.', '2024-10-01', NULL, 'Active', 620000.00),
    (2003, 'Brand Refresh', 'Update brand identity and digital assets.', '2025-02-01', '2025-11-30', 'Active', 180000.00),
    (2004, 'Mobile Application', 'Deliver a mobile application for customers.', '2025-03-01', NULL, 'Active', 520000.00),
    (2005, 'Employee Onboarding', 'Improve employee onboarding processes.', '2024-07-01', '2025-06-30', 'Completed', 95000.00),
    (2006, 'Cloud Migration', 'Migrate internal services to cloud hosting.', '2025-04-01', NULL, 'Active', 730000.00),
    (2007, 'Annual Budget Planning', 'Coordinate the upcoming annual budget cycle.', '2025-08-01', NULL, 'Planned', 60000.00),
    (2008, 'Website Accessibility', 'Improve accessibility across public websites.', '2025-05-15', NULL, 'On Hold', 125000.00),
    (2009, 'Supply Chain Optimization', 'Reduce delivery time and operating costs.', '2024-11-01', NULL, 'Active', 310000.00),
    (2010, 'Analytics Dashboard', 'Create operational and financial dashboards.', '2025-06-01', NULL, 'Planned', 240000.00);

INSERT INTO Employee_Project
    (employee_id, project_id, project_role, assigned_date, hours_per_week)
VALUES
    (1001, 2001, 'Backend Engineer', '2025-01-15', 20.00),
    (1001, 2002, 'Data Integration Engineer', '2025-02-01', 10.00),
    (1002, 2001, 'Technical Lead', '2025-01-15', 15.00),
    (1003, 2002, 'Database Engineer', '2024-10-01', 25.00),
    (1004, 2001, 'Quality Engineer', '2025-02-03', 12.00),
    (1005, 2005, 'Project Sponsor', '2024-07-01', 5.00),
    (1005, 2006, 'People Operations Lead', '2025-04-01', 5.00),
    (1006, 2005, 'Onboarding Coordinator', '2024-07-01', 15.00),
    (1007, 2005, 'Recruitment Advisor', '2024-07-08', 8.00),
    (1008, 2005, 'Training Designer', '2024-07-08', 10.00),
    (1009, 2009, 'Financial Sponsor', '2024-11-01', 5.00),
    (1009, 2010, 'Finance Lead', '2025-06-01', 8.00),
    (1010, 2009, 'Cost Analyst', '2024-11-04', 12.00),
    (1011, 2010, 'Reporting Accountant', '2025-06-02', 10.00),
    (1012, 2009, 'Budget Analyst', '2024-11-04', 6.00),
    (1013, 2003, 'Project Sponsor', '2025-02-01', 5.00),
    (1013, 2004, 'Marketing Lead', '2025-03-01', 8.00),
    (1014, 2003, 'Content Strategist', '2025-02-03', 15.00),
    (1015, 2004, 'Campaign Analyst', '2025-03-03', 10.00),
    (1016, 2003, 'Visual Designer', '2025-02-03', 12.00),
    (1017, 2001, 'Operations Sponsor', '2025-01-15', 4.00),
    (1017, 2009, 'Project Sponsor', '2024-11-01', 5.00),
    (1018, 2002, 'Business Analyst', '2024-10-01', 12.00),
    (1018, 2010, 'Operations Analyst', '2025-06-02', 10.00),
    (1019, 2005, 'Process Analyst', '2024-07-01', 8.00),
    (1019, 2007, 'Planning Coordinator', '2025-08-01', 10.00),
    (1020, 2008, 'Process Analyst', '2025-05-15', 8.00),
    (1020, 2010, 'Dashboard Analyst', '2025-06-02', 12.00);