-- Seed data for taxonomy review workbench (V1.14)

INSERT INTO kb_taxonomy_review_items (scope_code, l1_name, l2_name, l3_name, definition)
VALUES ('water', 'Billing', 'Payment', 'Invoice lookup', 'Find monthly invoices in the app.');
SET @item1 := LAST_INSERT_ID();
INSERT INTO kb_taxonomy_review_cases (review_item_id, content)
VALUES
  (@item1, 'User: How do I see last month invoice? Agent: Open Billing > History.'),
  (@item1, 'User: Where can I download invoice? Agent: Tap the invoice and choose Download.');

INSERT INTO kb_taxonomy_review_items (scope_code, l1_name, l2_name, l3_name, definition)
VALUES ('water', 'Service', 'Repair', 'Leak report', 'Report pipe leaks and request repair.');
SET @item2 := LAST_INSERT_ID();
INSERT INTO kb_taxonomy_review_cases (review_item_id, content)
VALUES
  (@item2, 'User: There is a pipe leak at home. Agent: Call the 24/7 hotline 963.'),
  (@item2, 'User: Can I report a leak online? Agent: Submit a repair ticket in the app.');

INSERT INTO kb_taxonomy_review_items (scope_code, l1_name, l2_name, l3_name, definition)
VALUES ('bus', 'Routes', 'Schedule', 'First bus time', 'Query the first departure time for a bus line.');
SET @item3 := LAST_INSERT_ID();
INSERT INTO kb_taxonomy_review_cases (review_item_id, content)
VALUES
  (@item3, 'User: What time is the first bus for Line 8? Agent: It departs at 06:00.'),
  (@item3, 'User: When does Line 3 start? Agent: First bus is at 05:50.');

INSERT INTO kb_taxonomy_review_items (scope_code, l1_name, l2_name, l3_name, definition)
VALUES ('bike', 'Membership', 'Account', 'Deposit refund', 'Request a deposit refund for bike membership.');
SET @item4 := LAST_INSERT_ID();
INSERT INTO kb_taxonomy_review_cases (review_item_id, content)
VALUES
  (@item4, 'User: How do I get my deposit back? Agent: Go to Wallet > Deposit Refund.'),
  (@item4, 'User: How long does refund take? Agent: Usually within 3-5 business days.');
