#include <iostream>
#include <string>
using namespace std;
class Student {
private:
    string name;
    int score;

public:
    Student(string n, int s) {
        name = n;
        score = s;
    }

    void setInfo(string n, int s) {
        name = n;
        score = s;
    }

    void display() {
        cout << "Name: " << name << ", Score: " << score << endl;
    }
};

int main() {
    Student students[3];

    students[0].setInfo("Zhang", 85);
    students[1].setInfo("Li", 92);
    students[2].setInfo("Wang", 78);

    for (int i = 0; i < 3; i++) {
        students[i].display();
    }

    return 0;
}