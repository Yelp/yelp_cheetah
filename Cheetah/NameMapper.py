"""This module supports Cheetah's optional NameMapper syntax.

Overview
================================================================================

NameMapper provides a simple syntax for accessing Python data structures,
functions, and methods from Cheetah. It's called NameMapper because it 'maps'
simple 'names' in Cheetah templates to possibly more complex syntax in Python.

Its purpose is to make working with Cheetah easy for non-programmers.
Specifically, non-programmers using Cheetah should NOT need to be taught (a)
what the difference is between an object and a dictionary, (b) what functions
and methods are, and (c) what 'self' is.  A further aim (d) is to buffer the
code in Cheetah templates from changes in the implementation of the Python data
structures behind them.

Consider this scenario:

You are building a customer information system. The designers with you want to
use information from your system on the client's website --AND-- they want to
understand the display code and so they can maintian it themselves.

You write a UI class with a 'customers' method that returns a dictionary of all
the customer objects.  Each customer object has an 'address' method that returns
the a dictionary with information about the customer's address.  The designers
want to be able to access that information.

Using PSP, the display code for the website would look something like the
following, assuming your servlet subclasses the class you created for managing
customer information:

  <%= self.customer()[ID].address()['city'] %>   (42 chars)

Using Cheetah's NameMapper syntax it could be any of the following:

   $self.customers()[$ID].address()['city']       (39 chars)
   --OR--
   $customers()[$ID].address()['city']
   --OR--
   $customers()[$ID].address().city
   --OR--
   $customers()[$ID].address.city
   --OR--
   $customers()[$ID].address.city
   --OR--
   $customers[$ID].address.city                   (27 chars)


Which of these would you prefer to explain to the designers, who have no
programming experience?  The last form is 15 characters shorter than the PSP
and, conceptually, is far more accessible. With PHP or ASP, the code would be
even messier than the PSP

This is a rather extreme example and, of course, you could also just implement
'$getCustomer($ID).city' and obey the Law of Demeter (search Google for more on that).
But good object orientated design isn't the point here.

Details
================================================================================
The parenthesized letters below correspond to the aims in the second paragraph.

DICTIONARY ACCESS (a)
---------------------

NameMapper allows access to items in a dictionary using the same dotted notation
used to access object attributes in Python.  This aspect of NameMapper is known
as 'Unified Dotted Notation'.

For example, with Cheetah it is possible to write:
   $customers()['kerr'].address()  --OR--  $customers().kerr.address()
where the second form is in NameMapper syntax.

This only works with dictionary keys that are also valid python identifiers:
  regex = '[a-zA-Z_][a-zA-Z_0-9]*'


AUTOCALLING (b,d)
-----------------

NameMapper automatically detects functions and methods in Cheetah $vars and calls
them if the parentheses have been left off.

For example if 'a' is an object, 'b' is a method
  $a.b
is equivalent to
  $a.b()

If b returns a dictionary, then following variations are possible
  $a.b.c  --OR--  $a.b().c  --OR--  $a.b()['c']
where 'c' is a key in the dictionary that a.b() returns.

Further notes:
* NameMapper autocalls the function or method without any arguments.  Thus
autocalling can only be used with functions or methods that either have no
arguments or have default values for all arguments.

* NameMapper only autocalls functions and methods.  Classes and callable object instances
will not be autocalled.

* Autocalling can be disabled using Cheetah's 'useAutocalling' setting.

LEAVING OUT 'self' (c,d)
------------------------

NameMapper makes it possible to access the attributes of a servlet in Cheetah
without needing to include 'self' in the variable names.  See the NAMESPACE
CASCADING section below for details.

NAMESPACE CASCADING (d)
--------------------
...

Implementation details
================================================================================

* NameMapper's search order is dictionary keys then object attributes

* NameMapper.NotFound is raised if a value can't be found for a name.

Cheetah uses the optimized C version (_namemapper.c) invariantly
"""

# pylint:disable=unused-import
from Cheetah._namemapper import NotFound  # noqa (intentionally unused)
from Cheetah._namemapper import valueForKey  # noqa (intentionally unused)
from Cheetah._namemapper import valueForName  # noqa (intentionally unused)
from Cheetah._namemapper import valueFromSearchList  # noqa (intentionally unused)
from Cheetah._namemapper import valueFromFrameOrSearchList  # noqa (intentionally unused)
from Cheetah._namemapper import valueFromFrame  # noqa (intentionally unused)
