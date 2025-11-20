"""
Tests for Flask routes
"""
import json


class TestAuthentication:
    """Test authentication routes"""

    def test_login_page_loads(self, client):
        """Test login page loads"""
        response = client.get('/login')
        assert response.status_code == 200
        assert b'login' in response.data.lower()

    def test_login_with_correct_password(self, client):
        """Test login with correct password"""
        response = client.post('/login', data={
            'password': 'test123'
        }, follow_redirects=True)

        assert response.status_code == 200
        # Should redirect to index after successful login

    def test_login_with_incorrect_password(self, client):
        """Test login with incorrect password"""
        response = client.post('/login', data={
            'password': 'wrongpassword'
        })

        assert response.status_code == 200
        assert b'Invalid password' in response.data or b'error' in response.data.lower()

    def test_logout(self, authenticated_client):
        """Test logout"""
        response = authenticated_client.get('/logout', follow_redirects=True)
        assert response.status_code == 200

    def test_protected_route_requires_login(self, client):
        """Test that protected routes redirect to login"""
        response = client.get('/transactions')
        assert response.status_code == 302  # Redirect
        assert 'login' in response.location.lower()


class TestIndexRoute:
    """Test index/dashboard route"""

    def test_index_requires_login(self, client):
        """Test index page requires authentication"""
        response = client.get('/')
        assert response.status_code == 302

    def test_index_loads_when_authenticated(self, authenticated_client):
        """Test index page loads for authenticated users"""
        response = authenticated_client.get('/')
        assert response.status_code == 200


class TestTransactionRoutes:
    """Test transaction-related routes"""

    def test_transactions_list(self, authenticated_client):
        """Test transactions list page"""
        response = authenticated_client.get('/transactions')
        assert response.status_code == 200

    def test_add_transaction_get(self, authenticated_client):
        """Test add transaction form loads"""
        response = authenticated_client.get('/transaction/add')
        assert response.status_code == 200

    def test_add_transaction_post(self, authenticated_client):
        """Test adding a manual transaction"""
        response = authenticated_client.post('/transaction/add', data={
            'date': '2025-03-15',
            'description': 'Test Manual Transaction',
            'amount': '-100.00',
            'category_id': '2',  # Technology category
            'notes': 'Test notes'
        }, follow_redirects=True)

        assert response.status_code == 200

    def test_edit_transaction_get(self, authenticated_client, db_session):
        """Test edit transaction form loads"""
        from src.database.models import Transaction

        trans = Transaction.query.first()
        if trans:
            response = authenticated_client.get(f'/transaction/{trans.id}/edit')
            assert response.status_code == 200

    def test_delete_transaction(self, authenticated_client, db_session):
        """Test deleting a transaction"""
        from src.database.models import Transaction

        trans = Transaction.query.first()
        if trans:
            response = authenticated_client.post(
                f'/transaction/{trans.id}/delete',
                follow_redirects=True
            )
            assert response.status_code == 200

            # Verify transaction is marked as deleted
            trans = Transaction.query.get(trans.id)
            assert trans.is_deleted is True

    def test_split_transaction_get(self, authenticated_client, db_session):
        """Test split transaction form loads"""
        from src.database.models import Transaction

        trans = Transaction.query.first()
        if trans:
            response = authenticated_client.get(f'/transaction/{trans.id}/split')
            assert response.status_code == 200


class TestTaxCalculatorRoutes:
    """Test tax calculator routes"""

    def test_tax_calculator_page_loads(self, authenticated_client):
        """Test tax calculator page loads"""
        response = authenticated_client.get('/tax_calculator')
        assert response.status_code == 200

    def test_calculate_tax_api(self, authenticated_client):
        """Test tax calculation API"""
        response = authenticated_client.post(
            '/api/calculate_tax',
            json={
                'start_date': '2025-03-01',
                'end_date': '2025-08-31',
                'age': 40,
                'medical_aid_members': 1,
                'previous_payments': '0'
            }
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'calculation' in data

    def test_calculate_tax_api_invalid_dates(self, authenticated_client):
        """Test tax calculation with invalid dates"""
        response = authenticated_client.post(
            '/api/calculate_tax',
            json={
                'start_date': 'invalid',
                'end_date': 'invalid',
                'age': 40,
                'medical_aid_members': 0,
                'previous_payments': '0'
            }
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False


class TestIncomeSourcesRoutes:
    """Test income sources management routes"""

    def test_income_sources_page_loads(self, authenticated_client):
        """Test income sources page loads"""
        response = authenticated_client.get('/income_sources')
        assert response.status_code == 200

    def test_add_income_source(self, authenticated_client, db_session):
        """Test adding an income source pattern"""
        from src.database.models import Category

        income_cat = Category.query.filter_by(name='Income').first()

        response = authenticated_client.post(
            '/api/income_source/add',
            json={
                'pattern': 'PAYPAL',
                'category_id': income_cat.id,
                'is_regex': False,
                'priority': 100
            }
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True

    def test_toggle_income_source(self, authenticated_client, db_session):
        """Test toggling income source active status"""
        from src.database.models import ExpenseRule

        rule = ExpenseRule.query.first()
        if rule:
            original_status = rule.is_active

            response = authenticated_client.post(
                f'/api/income_source/{rule.id}/toggle'
            )

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert data['is_active'] != original_status

    def test_delete_income_source(self, authenticated_client, db_session):
        """Test deleting an income source pattern"""
        from src.database.models import ExpenseRule, Category

        # Create a test rule to delete
        income_cat = Category.query.filter_by(name='Income').first()
        test_rule = ExpenseRule(
            pattern='TEST DELETE',
            category_id=income_cat.id,
            priority=50,
            is_regex=False,
            is_active=True
        )
        db_session.add(test_rule)
        db_session.commit()

        response = authenticated_client.post(
            f'/api/income_source/{test_rule.id}/delete'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True

        # Verify rule is deleted
        rule = ExpenseRule.query.get(test_rule.id)
        assert rule is None


class TestDuplicatesRoutes:
    """Test duplicate detection routes"""

    def test_duplicates_page_loads(self, authenticated_client):
        """Test duplicates page loads"""
        response = authenticated_client.get('/duplicates')
        assert response.status_code == 200

    def test_mark_duplicate_api(self, authenticated_client, db_session):
        """Test marking a transaction as duplicate"""
        from src.database.models import Transaction

        # Get two transactions
        trans = Transaction.query.limit(2).all()
        if len(trans) >= 2:
            response = authenticated_client.post(
                '/api/mark_duplicate',
                json={
                    'transaction_id': trans[1].id,
                    'duplicate_of_id': trans[0].id
                }
            )

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True

            # Verify transaction is marked as duplicate
            trans1 = Transaction.query.get(trans[1].id)
            assert trans1.is_duplicate is True
            assert trans1.duplicate_of_id == trans[0].id
