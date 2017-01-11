import re
from sqlalchemy import or_, and_
from .models import Entity
from .exceptions import ColumnNotFoundException, ColumnOperatorNotFoundException
from sqlalchemy import exc

class QueryFilter():
	
	REGEX_COLUMN_OPERATORS = r'\s+(\w+)\s+'

	def create_filters(expr_dict, model, validate_values = 0):
		
		sql_filter_set = list()

		try:
			
			if expr_dict['priority_filters'] is not None:
				
				for key in expr_dict['priority_filters']:
				
					expr_list = key['expr']
					op = QueryFilter.get_sql_operator(key['op'])
					sql_filter = list()

					for expr in expr_list:
					
						column_operator = QueryFilter.parse_column_operator(expr)
						sql_filter.append(QueryFilter.get_filter_expression(expr.strip(), column_operator, model))
					sql_filter_set.append(op(*sql_filter))
			
			sql_filter = list()
			
			op = None
			
			if expr_dict['simple_filters']['op'] is not None:
				op = QueryFilter.get_sql_operator(expr_dict['simple_filters']['op'])
				
			
			if expr_dict['simple_filters']['expr'] is None:
				return op(*sql_filter_set)
			
			else:

				for key in expr_dict['simple_filters']['expr']:
				
					column_operator = QueryFilter.parse_column_operator(key)
					sql_filter.append(QueryFilter.get_filter_expression(key.strip(), column_operator, model))	
				
				if op is None:
					return sql_filter
				else:
					return (op(*sql_filter_set,*sql_filter))
				

		except KeyError:
			print("Filter type not defined")
			return None

	def get_sql_operator(op):
		
		if op == 'and':
			return and_
		
		elif op == 'or':
			return or_
		
		else:
			return None
	
	def parse_column_operator(exp):
		
		exp = exp.strip()
		op = re.search(QueryFilter.REGEX_COLUMN_OPERATORS, exp, flags = re.I)

		if op is None:
			print("No Opeator Found")
			return None
		
		else:
			return op.group().strip()

	def get_filter_expression(expression, op, model):

		column, value = re.split(r'\s%s\s' % op, expression)
		
		column = column.replace('(','')
		column = column.replace(')','')
		column = column.replace(' ','')
		
		value = value.replace('(','')
		value = value.replace(')','')
		value = value.replace(' ','')

		field = getattr(model, column, None)

		if field is None:
			raise ColumnNotFoundException(column)
		
		attr = list(filter(
						lambda e: hasattr(field, e % op), 
						['%s','%s_','__%s__']
					  ))
		
		if not attr:
			raise ColumnOperatorNotFoundException(op)
		
		attr = attr[0] %op
		return getattr(field, attr)(value)
