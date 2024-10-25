from flask import Flask, request, jsonify, render_template
from pymongo import MongoClient
import ast
from datetime import datetime

app = Flask(__name__)

# MongoDB client setup
client = MongoClient('mongodb://localhost:27017')  # Update with your connection string if needed
db = client['rules_database']  # Database name
rules_collection = db['rules']  # Collection name

class Node:
    """Custom class to represent nodes in an AST"""
    def __init__(self, node_type, left=None, operator=None, right=None):
        self.node_type = node_type
        self.left = left
        self.operator = operator
        self.right = right

    def __repr__(self):
        return f"Node(type={self.node_type}, left={self.left}, operator={self.operator}, right={self.right})"

def create_rule_ast(rule_string):
    try:
        # Convert 'AND'/'OR' to 'and'/'or' for Python parsing
        rule_string = rule_string.replace('AND', 'and').replace('OR', 'or')

        # Use regex to convert single '=' to '==', but avoid assignments
        import re
        rule_string = re.sub(r'(?<![=!<>])=(?!=)', '==', rule_string)  # Convert `=` to `==` for comparisons

        if not balanced_parentheses(rule_string):
            raise SyntaxError(f"Unbalanced parentheses in rule: {rule_string}")

        expr_ast = ast.parse(rule_string, mode='eval')
        return convert_ast(expr_ast.body)
    except SyntaxError as e:
        print(f"Syntax error in rule: {rule_string} -> {e}")
        return None


def balanced_parentheses(rule_string):
    stack = []
    for char in rule_string:
        if char == "(":
            stack.append(char)
        elif char == ")":
            if not stack:
                return False
            stack.pop()
    return len(stack) == 0

def convert_ast(node):
    if isinstance(node, ast.BoolOp):
        operator = 'AND' if isinstance(node.op, ast.And) else 'OR'
        left = convert_ast(node.values[0])
        right = convert_ast(node.values[1])
        return Node(node_type='logical', left=left, operator=operator, right=right)

    elif isinstance(node, ast.Compare):
        left = convert_ast(node.left)
        operator = convert_operator(node.ops[0])
        right = convert_ast(node.comparators[0])
        return Node(node_type='comparison', left=left, operator=operator, right=right)

    elif isinstance(node, ast.Name):
        return node.id

    elif isinstance(node, ast.Constant):
        return node.value

def convert_operator(op):
    if isinstance(op, ast.Gt):
        return '>'
    elif isinstance(op, ast.Lt):
        return '<'
    elif isinstance(op, ast.Eq):
        return '='
    else:
        raise ValueError(f"Unsupported operator: {type(op).__name__}")

def pretty_print_node(node, indent=0):
    """Recursively pretty-print the Node structure."""
    indent_str = ' ' * indent
    if isinstance(node, Node):
        result = f"{indent_str}Node(type={node.node_type},\n"
        result += pretty_print_node(node.left, indent + 2) + ",\n"
        result += f"{indent_str}  operator={node.operator},\n"
        result += pretty_print_node(node.right, indent + 2) + "\n"
        result += f"{indent_str})"
        return result
    else:
        return indent_str + str(node)

@app.route('/save_rule', methods=['POST'])
def save_rule():
    data = request.json
    attribute = data.get('attribute')
    operator = data.get('operator')
    value = data.get('value')
    combined_rule = data.get('combined_rule')

    if not combined_rule:
        return jsonify({'error': 'No combined rule provided'}), 400

    # Create a new rule document
    rule_document = {
        'attribute': attribute,
        'operator': operator,
        'value': value,
        'combined_rule': combined_rule,
        'created_at': datetime.utcnow()
    }

    # Insert the rule into MongoDB
    result = rules_collection.insert_one(rule_document)

    return jsonify({'success': True, 'rule_id': str(result.inserted_id)})




@app.route('/evaluate')
def evaluate_rules():
    # Fetch rules from MongoDB
    rules = list(rules_collection.find())
    return render_template('evaluate.html', rules=rules)

def evaluate_rule(ast_representation, data):
    if ast_representation.node_type == 'logical':
        left_result = evaluate_rule(ast_representation.left, data)
        right_result = evaluate_rule(ast_representation.right, data)
        if ast_representation.operator == 'AND':
            return left_result and right_result
        elif ast_representation.operator == 'OR':
            return left_result or right_result

    elif ast_representation.node_type == 'comparison':
        left_value = data.get(ast_representation.left)
        right_value = ast_representation.right
        if ast_representation.operator == '>':
            return left_value > right_value
        elif ast_representation.operator == '<':
            return left_value < right_value
        elif ast_representation.operator == '=':
            return left_value == right_value

    return False  # Default case for unsupported node types


@app.route('/create_ast', methods=['POST'])
def create_ast_route():
    data = request.json
    combined_rule = data.get('combined_rule')

    if not combined_rule:
        return jsonify({'error': 'No combined rule provided'}), 400

    # Create the AST from the combined rule
    ast_representation = create_rule_ast(combined_rule)

    if ast_representation:
        pretty_ast = pretty_print_node(ast_representation)
        print(pretty_ast)  # Output the formatted AST to the terminal

        # Store the combined rule and its AST in MongoDB
        rule_document = {
            'combined_rule': combined_rule,
            'ast_representation': pretty_ast,
            'created_at': datetime.utcnow()
        }

        result = rules_collection.insert_one(rule_document)  # Insert into MongoDB
        return jsonify({'ast': pretty_ast, 'rule_id': str(result.inserted_id)})
    else:
        return jsonify({'error': 'Invalid rule syntax'}), 400



@app.route('/create-rule')  # Original route for creating rules
def create_rule():
    return render_template('create-rule.html')



    

@app.route('/display-evaluate', methods=['GET'])
def display_evaluate_page():
    # Fetch the rules from MongoDB (assuming 'rules_collection' is your collection)
    rules = list(rules_collection.find({}, {"_id": 0, "combined_rule": 1}))
    
    # Debugging: Print the fetched rules in the console
    print("Fetched rules from MongoDB:", rules)
    
    # Check if any rules are available
    if not rules:
        print("No rules found in the database.")
    else:
        print(f"Rules available: {rules}")

    # Pass the fetched rules to the template
    return render_template('evaluate.html', rules=rules)




@app.route('/evaluate-rule', methods=['POST', 'GET'])
def evaluate_rule_logic():
    if request.method == 'POST':
        # Add your logic here to evaluate the rule
        data = request.json
        # Example of evaluating the rule logic based on the data
        # You can customize this logic as per your needs.
        return jsonify({'result': 'Rule evaluation successful'})
    return render_template('evaluate.html')  # Render your evaluate rule form on GET request







@app.route('/')
def home():
    return render_template('home.html')

if __name__ == '__main__':
    app.run(debug=True)
