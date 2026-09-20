import accountz

#----------------------------------------------------------------------
# testing suit
#----------------------------------------------------------------------
if __name__ == '__main__':
    def test1():
        print("Testing accountz_demo.py")
        db = accountz.AccountLocal('D:/local/share/accountz.db')
        print(db.register('skywind@tuohn.com', '1234', 'linwei', 1, 'xx'))
        print(db.population(100))
        print(db.login('skywind@tuohn.com', '1234'))
        print(db.login('skywind@tuohn.com', '1'))
        print(db.login('skywind@tuohn.com', None))
        print(db.login('skywind@tuohn.com', None, force = True))
        return 0

    test1()

