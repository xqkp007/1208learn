-- V1.12 分类知识库（kb_taxonomy）建表脚本
-- scope_code: water|bus|bike

CREATE TABLE IF NOT EXISTS kb_taxonomy_nodes (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  scope_code VARCHAR(16) NOT NULL COMMENT 'water|bus|bike',
  level TINYINT NOT NULL COMMENT '1|2|3',
  name VARCHAR(128) NOT NULL,
  parent_id BIGINT NULL,
  definition TEXT NULL COMMENT 'Only level=3',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_kb_taxonomy_nodes_scope_parent (scope_code, parent_id),
  UNIQUE KEY uq_kb_taxonomy_nodes_scope_parent_name (scope_code, parent_id, name),
  CONSTRAINT fk_kb_taxonomy_parent FOREIGN KEY (parent_id) REFERENCES kb_taxonomy_nodes(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS kb_taxonomy_cases (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  node_id BIGINT NOT NULL,
  content MEDIUMTEXT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_kb_taxonomy_cases_node (node_id),
  CONSTRAINT fk_kb_taxonomy_cases_node FOREIGN KEY (node_id) REFERENCES kb_taxonomy_nodes(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

