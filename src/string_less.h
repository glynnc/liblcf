/*
 * Copyright (c) 2014 liblcf authors
 * This file is released under the MIT License
 * http://opensource.org/licenses/MIT
 */

#ifndef LCF_STRING_LESS_H
#define LCF_STRING_LESS_H

class string_less {
public:
	bool operator()(const char *, const char *) const;
};

#endif

