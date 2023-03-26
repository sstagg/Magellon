from flask_restful import Resource


class Math(Resource):

    def get(self, num1, num2, operation):
        result = None
        if operation == 'add':
            result = num1 + num2
        elif operation == 'multiply':
            result = num1 * num2
        return {'result': result}

    def get(self, num1, num2):
        return {'result': num1 + num2}

    def get_add(self, num1, num2):
        return {'result': num1 + num2}

    def get_multiply(self, num1, num2):
        return {'result': num1 * num2}
