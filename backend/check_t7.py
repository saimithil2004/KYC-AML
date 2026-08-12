import sqlite3

conn = sqlite3.connect('test_ci_db.db')
c = conn.cursor()

# Get column names for risk_scores
c.execute("PRAGMA table_info(risk_scores)")
cols = [row[1] for row in c.fetchall()]
print('risk_scores columns:', cols)

c.execute("SELECT id, first_name, last_name, status, nationality, country FROM customers WHERE first_name='Missing' AND last_name='KYC Test' ORDER BY created_at DESC LIMIT 1")
r = c.fetchone()
if r:
    print()
    print('Customer:', r)
    cust_id = r[0]
    
    c.execute('SELECT occupation, tax_residency, source_of_funds, source_of_wealth FROM kyc_profiles WHERE customer_id=?', (cust_id,))
    kyc = c.fetchone()
    print('KYC (occupation, tax_residency, source_of_funds, source_of_wealth):', kyc)
    
    c.execute('SELECT id, status, priority FROM cases WHERE customer_id=? ORDER BY created_at DESC', (cust_id,))
    cases = c.fetchall()
    print('Cases:', cases)
    
    c.execute(f'SELECT {", ".join(cols)} FROM risk_scores WHERE customer_id=?', (cust_id,))
    risk = c.fetchone()
    print('Risk score:', dict(zip(cols, risk)) if risk else None)
    
    c.execute('SELECT alert_type FROM alerts WHERE customer_id=?', (cust_id,))
    alerts = c.fetchall()
    print('Alerts:', alerts)
    
    c.execute('SELECT document_type, verification_status FROM documents WHERE customer_id=?', (cust_id,))
    docs = c.fetchall()
    print('Docs:', docs)

conn.close()
