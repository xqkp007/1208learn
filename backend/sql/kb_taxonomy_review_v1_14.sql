-- V1.14 taxonomy review workbench schema
CREATE TABLE IF NOT EXISTS kb_taxonomy_review_items (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  scope_code VARCHAR(16) NOT NULL COMMENT 'water|bus|bike',
  l1_name VARCHAR(128) NOT NULL,
  l2_name VARCHAR(128) NOT NULL,
  l3_name VARCHAR(128) NOT NULL,
  definition TEXT NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT 'pending|accepted|discarded',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_kb_taxonomy_review_scope_status (scope_code, status)
);

CREATE TABLE IF NOT EXISTS kb_taxonomy_review_cases (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  review_item_id BIGINT NOT NULL,
  content TEXT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_kb_taxonomy_review_cases_item (review_item_id),
  CONSTRAINT fk_kb_taxonomy_review_cases_item
    FOREIGN KEY (review_item_id) REFERENCES kb_taxonomy_review_items(id) ON DELETE CASCADE
);
