Installation and Running
=========================================

Environment Variables
^^^^^^^^^^^^^^^^^^^^^
 
 - DATABASE_URL = ``<yourdburi>``
 - FLASK_APP = ``wsgi.py``
 - FLASK_DEBUG = ``True/False``

Clone the repository
^^^^^^^^^^^^^^^^^^^^

``git clone https://github.com/sohaibfarooqi/stargate.git``

Create VirtualEnv
^^^^^^^^^^^^^^^^^

 - ``virtualenv -p "/path/to/python" env``
 - ``source env/bin/activate``

Install Dependencies
^^^^^^^^^^^^^^^^^^^^

``pip install -r requirements.txt``

Run Migrations
^^^^^^^^^^^^^^

 - ``flask db migrate``
 - ``flask db upgrade``

Running
^^^^^^^

``flask run``
