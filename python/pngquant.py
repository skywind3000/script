import sys
import os


#----------------------------------------------------------------------
# 
#----------------------------------------------------------------------
def pngquant(dirname):
    if not os.path.isdir(dirname):
        print("Directory not found")
        return 1
    dirname = os.path.abspath(dirname)
    pending = []
    print(f'scaning {dirname} ...')
    for root, dirs, files in os.walk(dirname):
        for file in files:
            fn = os.path.normcase(file)
            if fn.endswith('.png'):
                pending.append(os.path.join(root, file))
            elif fn.endswith('.jpg') or fn.endswith('.jpeg'):
                pending.append(os.path.join(root, file))
    for file in pending:
        file = os.path.abspath(file)
        dirname = os.path.dirname(file)
        filename = os.path.basename(file)
        os.chdir(dirname)
        fn = os.path.normcase(file)
        if fn.endswith('.png'):
            cmd = f'pngquant --ext .png --force --speed 1 --quality 60-80 "{filename}"'
            print(file)
            os.system(cmd)
        elif fn.endswith('.jpg') or fn.endswith('.jpeg'):
            cmd = f'jpegoptim -s -m 80 "{filename}"'
            print(file)
            os.system(cmd)
    return 0


#----------------------------------------------------------------------
# testing suit
#----------------------------------------------------------------------
if __name__ == '__main__':
    def test1():
        # pngquant('E:/site/images/p/tcz_cd')
        # pngquant('E:/site/images/p')
        # pngquant('E:/site/skywind3000.github.io/word/images')
        return 0
    test1()


