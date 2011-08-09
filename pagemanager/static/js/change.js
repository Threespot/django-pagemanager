(function($){

    $(function(){

        $('input#id_title').attr('placeholder', 'Title');

        (function(){

            return {

                // init each piece of functionality
                'init': function(){
                    window.app = this;
                    for(piece in this){
                        if(piece !== 'init') this[piece].init();
                    }
                },

                'orderInlines': {
                    '$groups': $('.inline-group'),
                    'makeSortLink': function(){
                        return $('<a></a>', {
                            'href': '#',
                            'click': this.toggleSortable,
                            'text': 'Sort'
                        });
                    },
                    'enumerate': function(){
                        var self = app.orderInlines;
                        self.$groups.each(function(index, element){
                            $(element).find('.inline-related').each(function(index, element){
                                $(element).find('input[id$="order"]').val(index+1);
                            });
                        });
                    },
                    'startSortable': function($group){
                        var self = app.orderInlines,
                            makeSummary = function(element){
                                var text = $(element).find('input[type="text"]:first').val()
                                return $('<div></div>', {
                                    'class': 'summary',
                                    'html': $('<span></span>', {
                                        'text': Boolean(text) ? text : 'Untitled'
                                    })
                                });
                            };
                        $group.addClass('sorting');
			$group.find('h2 a').text('Finish Sort');
                        $group.find('.inline-related').each(function(index, element){
                            makeSummary(element).appendTo(element);
                        });
                        $group.sortable('enable');
                    },
                    'stopSortable': function($group){
                        var self = app.orderInlines;
                        $group.find('.summary').remove();
			$group.find('h2 a').text('Sort');
                        $group.removeClass('sorting');
                        $group.sortable('disable');
                    },
                    'toggleSortable': function(evt){
                        evt.preventDefault();
                        var self = app.orderInlines,
                            $group = $(this).closest('.inline-group');
                        if(self.sorting){
                            self.stopSortable($group);
                            self.sorting = false;
                        }else{
                            self.startSortable($group);
                            self.sorting = true;
                        }
                    },
                    'init': function(){
                        var self = this;
                        this.enumerate();
                        this.sorting = false;
                        this.$groups.each(function(index, element){
                            $element = $(element);
                            console.log($element);
                            app.orderInlines.makeSortLink().appendTo($element.find('h2'));
                            $element.sortable({
                                'items': '.inline-related',
                                'handle': '.summary',
                                'stop': self.enumerate
                            });
                            $element.find('span').disableSelection();
                            $element.sortable('disable');
                        });
                    }
                },

                'slugToggle': {
                    '$container': $('fieldset.basics div.slug'),
                    'generate_form': function(){
                        var form = $('<div></div>', {
                            'class': 'form'
                        });
                        this.$input.appendTo(form);
                        var list = $('<ul></ul>', {
                            'class': 'object-tools'
                        }).appendTo(form);
                        var listItem = $('<li></li>').appendTo(list);
                        var ok = $('<a></a>', {
                            'href': '#',
                            'text': 'OK',
                            'click': function(evt){
                                evt.preventDefault();
                                app.slugToggle.toggle();
                            }
                        }).appendTo(listItem);
                        return form;
                    },
                    'generate_edit_link': function(){
                        var listItem = $('<li></li>');
                        var edit = $('<a></a>', {
                            'href': '#',
                            'text': 'Edit',
                            'click': function(evt){
                                evt.preventDefault();
                                app.slugToggle.toggle();
                            }
                        }).appendTo(listItem);
                        return listItem
                    },
                    'open': function(){
                        this.isOpen = true;
                        this.$container.addClass('open')
                    },
                    'close': function(){
                        this.isOpen = false;
                        this.$container.removeClass('open')
                    },
                    'toggle': function(){
                        if(this.isOpen){
                            this.close();
                        }else{
                            this.open();
                        }
                    },
                    'reset': function(){
                        this.$input.val(this.$input[0].defaultValue);
                    },
                    'sanitize': function(str){
                        return str.toLowerCase().replace(/\s/gi, '-').replace(/[^a-z0-9-]/gi, '');
                    },
                    'sanitizeValue': function(){
                        if($(this).val() == '') $(this).val(this.defaultValue);
                        $(this).val(app.slugToggle.sanitize($(this).val()));
                    },
                    'updateText': function(){
                        var val = $(this).val();
                        if(val == '') val = this.defaultValue;
                        app.slugToggle.$text.text(app.slugToggle.sanitize(val));
                    },
                    'init': function(){
                        this.$container.addClass('active');
                        if(!this.$container.find('.add').length){
                            this.$text = this.$container.find('.text');
                            this.$input = this.$container.find('input[type="text"]');
                            this.$form = this.generate_form().insertAfter(this.$text);
                            this.$tools = this.$container.find('> div > .object-tools');
                            this.$editLink = this.generate_edit_link().prependTo(this.$tools);
                            this.$input.keyup(this.updateText);
                            this.$input.blur(this.sanitizeValue);
                            this.close();
                        }
                    }
                }

            };

        })().init();

    });

})(django.jQuery);
