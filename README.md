# COMS 6156 - TestInProd
### Project Overview
TestInProd is a testing framework that aims to improve developer experience in writing testcases by capturing function executions and automatically generating testcases from those executions.

### Usage Instructions
Prerequisites:
- Python3 must be used for the project you wish to test and for use of the framework.
- Pip (a tool for installing python packages) is strongly encouraged.
- Autopep8 (a tool for formatting the written testcases) must be installed. Can be easily installed with "pip3 install autopep8"

Usage:
- Clone the project into your project directory directory.
- In the file in which you want to use the framework, import "track\_class" from "pytest.test\_in\_prod"
- Annotate the class you wish to track with "@track\_class()".
- Now run an execution on the functionality that was annotated. It will result in a unittest file with the name "test\_" and the filename.
- For more features, experiment with "@track\_class(thorough=True, trusted=False)" to enable thorough mode and disable trusted mode.

