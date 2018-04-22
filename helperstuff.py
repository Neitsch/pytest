from test_in_prod import track_class

@track_class(thorough=True, trusted=False)
class HelperClass(object):
    def __init__(self, number=6):
        self.hello = []
        self.hello.append(number)

    def my_func(self, lst):
        lst.extend(self.hello)
        print('Was I called?' + str(lst))
        return lst

    '''
    def another_func(self, str_val):
        return str_val
    '''
